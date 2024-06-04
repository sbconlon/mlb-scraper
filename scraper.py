# External imports
import datetime
import pytz
import time

# Internal imports
from soup import Soup, SoupParser
from game import GameState
from lines import LineGenerator

class Scraper:

    # Key assumptions:
    # 1) Games can't move backward in time.
    #        If we have a in-memory game object that is final and we get a new
    #        game state with a matching id prefix, then we must assume the new
    #        soup corresponds to a new, different game, double header scenario.
    # 2) Games can't have multiple start times.
    #        If we have a in-memory game object that has a different start time
    #        than a game update with the same game id prefix, then we must have
    #        a new game, double header scenario.
    # 3) Two games with the same id prefix can't be live at the same time.
    #        Double headers can not be concurrent, this would not make sense.
    #        Therefore, if we have a live game update with a prefix that matches
    #        multiple game ids, then it should be applied to the game that's
    #        active.
    # 4) The same game can not be updated more than once per iteration. This is
    #        a safe assumption as its unlikely for the same game to be scraped twice
    #        off the mlb.com website. And it helps resolve some double-header edge
    #        cases.

    def __init__(self, dumper, generator, alerter, logger):
        # Dumps data out
        self.dumper = dumper
        # Generates game lines
        self.linegen = generator
        # Issue alerts
        self.alerter = alerter
        # Log
        self.logger = logger
        #
        # Game states
        # Games should transition from: pregame -> live -> final
        # They can not go backward.
        #
        # Maps: Game ID (str) -> GameState
        self.games = {
                        'pregame': {},
                        'live': {},
                        'final': {}
                     }
        # Set of ids for games that have been updated this iteration.
        self.updated = set()

    # This function logs and issues an alert.
    def notify(self, message):
        self.logger.log(message)
        self.alerter.alert(message)

    # The lookup functions take a game prefix and match it to a game in the
    # games dictionary, or constructs a new game if a match is not found.
    #
    # Returns the GameState for the given prefix.

    # Looks up prefix in a given games dictionary
    # bucket in the set('pregame', 'live', 'final')
    def match(self, bucket, prefix):
        return [id for id in self.games[bucket].keys() if id[:-1] == prefix]

    # Lookup live games that match the prefix.
    def lookup_live(self, prefix):
        # First, check if the prefix matches a game in the live game hash.
        live_matches = self.match('live', prefix)
        if live_matches:
            # If we have a match then return the GameState.
            assert(len(live_matches) == 1) # Assumption 3
            assert(not live_matches[0] in self.updated) # Assumption 4
            return self.games['live'][live_matches[0]]
        # Second check if the prefix matches a game in the pregame hash.
        pregame_matches = self.match('pregame', prefix)
        if pregame_matches:
            # If we have multiple matches then take the game with the earliest
            # start time.
            return sorted([self.games['pregame'][id] for id in pregame_matches],
                           key=lambda game: game.start_time)[0]
        # Else, we need to create a new game
        id = GameState.new_game_id(prefix)
        self.notify(f'CREATING NEW LIVE GAME {id}')
        self.games['live'][id] = GameState(id)
        return self.games['live'][id]

    # Lookup games in the pregame hash.
    #
    # NOTE - Need to fix the edge case where a double header is created
    #        in a single iteration, and the second game has a delayed start.
    #        Currently, we would change the first game's start time to the second
    #        start time, then upon the second iteration we would create another GameState
    #        for the first game but incorrectly assign it the '1' id suffix.
    #
    def lookup_pregames(self, prefix, start, delayed):
        # Check for prefix matches in the pregame hash.
        prefix_matches = self.match('pregame', prefix)
        # If we have prefix matches...
        if prefix_matches:
            # Get the game with the matching start time.
            candidate = [id for id in prefix_matches
                            if self.games['pregame'][id].start_time == start]
            # If we don't have a matching start time and the game's start time has
            # been delayed, then we update the game with the matching prefix's start time.
            #
            # Note: if there are multiple games with a matching prefix, then we choose the
            #       game with the closest start time before the new start time.
            #       (This assumes game times can't be moved forward which might not be true)
            #
            # Fix: Enforce the rule that a game can only be updated once per iteration.
            #      Therefore, if we see the second game in a double header that's been delayed,
            #      then we know to create a new game.
            if (not candidate) and delayed:
                valid_games = [id for id in prefix_matches if not id in self.updated]
                candidate = [min(valid_games,
                                 key=lambda id: abs(start-self.games['pregame'][id].start_time))]
            assert(len(candidate) <= 1) # Match should be unique (or zero).
            if candidate and not candidate[0] in self.updated:
                return self.games['pregame'][candidate[0]]
        # Else, if we have no prefix + start time matches, then make a new game.
        id = GameState.new_game_id(prefix)
        self.notify(f'CREATING NEW PREGAME {id}')
        self.games['pregame'][id] = GameState(id)
        return self.games['pregame'][id]

    # Lookup games in the final hash.
    def lookup_final(self, prefix):
        # First, check for prefix matches in the final hash.
        final_matches = self.match('final', prefix)
        # We can have multiple matches here if both games of a double header have
        # concluded. It doesn't matter, so we return the first game in the
        # match list.
        if final_matches:
            return self.games['final'][final_matches[0]]
        # Second, check for live games that may have finished.
        live_matches = self.match('live', prefix)
        # Live game prefixes must be unique.
        # We can't have the same team playing two games at the same time.
        if live_matches:
            assert(len(live_matches) == 1)
            return self.games['live'][live_matches[0]]
        # Third, check pregames hash.
        # This should be rare.
        pre_matches = self.match('pregame', prefix)
        # There is some ambiguity here which game to use since we don't have
        # start time in a final game soup, so we take the game with the
        # earliest start time.
        if pre_matches:
            return sorted([self.games['pregame'][id] for id in pre_matches],
                        key=lambda g: g.start_time)[0]
        # Else, we create a new game.
        id = GameState.new_game_id(prefix)
        self.notify(f'CREATING NEW FINAL GAME {id}')
        self.games['final'][id] = GameState(id)
        return self.games['final'][id]

    # Move the game with id from 'from' to 'to'.
    allowed_txn = set((('pregame', 'live'),
                       ('live', 'final'),
                       ('pregame', 'final')))
    def transition(self, id, orig, dest):
        # Check that the given states are valid
        assert(orig in self.games.keys() and dest in self.games.keys())
        # Check that the transition is allowed.
        assert((orig, dest) in Scraper.allowed_txn)
        # Check that a game with the same id isn't in our destination state.
        assert(not id in self.games[dest].keys())
        # Move the game
        self.games[dest][id] = self.games[orig][id]
        del self.games[orig][id]

    # Returns the time until the next game starts in seconds.
    # With a 30 min buffer for late start games, in which case 30 secs is returned.
    def time_until_next_game(self, lines):
        # Get the current time, in eastern timezone.
        nowtime = datetime.datetime.now().astimezone(pytz.timezone('US/Pacific'))
        # Get the next game start time, in pacific timezone, filtered s.t. we exclude games
        # that have already started.
        # Note: Give a 30min buffer for games that start later than their listed start time.
        gametime = min([start_time for start_time, _ in lines.values() if 

























































                            start_time > nowtime-datetime.timedelta(minutes=30)])
        # Calculate the difference in seconds.
        secs = (gametime - nowtime).total_seconds()
        # If a game is starting later than its listed time then secs will be negative.
        # Instead, we want to wait thirty seconds.
        return secs if secs > 0 else 30

    def scrape(self):
        tz = pytz.timezone('US/Pacific')
        webpage = Soup()
        while True:
            self.logger.log(f"---> {datetime.datetime.now(tz).strftime('%m/%d/%Y')} {datetime.datetime.now(tz).strftime('%H:%M:%S')}")

            # Time the soup was brewed and lines were generated.
            timestamp = datetime.datetime.now(tz)
            # Get current lines.
            lines = self.linegen.get_lines()

            # Initialize updated set to empty at the start of an iteration.
            self.updated = set()

            # Each game has its own soup that we must process.
            for soup in webpage.brew():
                # Get the game id prefix for the game soup
                teams = SoupParser.get_teams(soup)
                prefix = GameState.get_id_prefix(teams[1])
                #
                # Parse warmup games
                if SoupParser.is_warmup(soup):
                    continue # Skip warmup games
                #
                # Parse live game update
                elif SoupParser.is_live(soup):
                    # Find the GameState for the corresponding prefix
                    game = self.lookup_live(prefix)
                    # Transition the game from pregame to live, if needed.
                    if game.id in self.games['pregame'].keys():
                        self.notify(f'TRANSITIONING {game.id} from pregame to live')
                        self.transition(game.id, 'pregame', 'live')
                    # Update game state
                    game.update(timestamp,
                                SoupParser.parse_live(soup),
                                lines.get(prefix, (None, None))[1])
                    # Add to updated set.
                    self.updated.add(game.id)
                    # Dump game state and line info
                    self.dumper.dump_state(game)
                    if not game.line_info is None:
                        self.dumper.dump_lines(game)
                    # Log
                    self.logger.log('---------------------------------------------------')
                    self.logger.log(str(game))
                    self.logger.log()
                #
                # Parse pre game info
                elif SoupParser.is_pregame(soup):
                    # Find the GameState for the corresponding prefix.
                    # Account for a change in start time for delayed games.
                    start_time = SoupParser.get_start_time(soup)
                    game = self.lookup_pregames(prefix, start_time, SoupParser.is_delayed(soup))
                    # Set start time if its not already set.
                    if not game.start_time:
                        game.start_time = start_time
                    # Add to updated set.
                    self.updated.add(game.id)
                #
                # Parse post game or postponed game info.
                elif (SoupParser.is_final(soup) or
                      SoupParser.is_postponed(soup) or
                      SoupParser.is_suspended(soup)):
                    # Find the GameState for the corresponding prefix
                    game = self.lookup_final(prefix)
                    # Notify if a live game is postponed or suspended.
                    if game.id in self.games['live'].keys() and SoupParser.is_postponed(soup):
                        self.notify(f'POSTPONED {game.id}')
                    if game.id in self.games['live'].keys() and SoupParser.is_suspended(soup):
                        self.notify(f'SUSPENDED {game.id}')
                    # Move the game to the final hash, if needed.
                    if game.id in self.games['pregame'].keys():
                        self.notify(f'TRANSITIONING {game.id} from pregame to final')
                        self.transition(game.id, 'pregame', 'final')
                    elif game.id in self.games['live'].keys():
                        self.notify(f'TRANSITIONING {game.id} from live to final')
                        self.transition(game.id, 'live', 'final')
                    # Add to updated set
                    self.updated.add(game.id)
                else:
                    self.notify('WARNING: Couldnt identify the game soup.')

            # Print line API usage statistics
            stats = self.linegen.usage()
            self.logger.log('Remaining: ' + str(stats[0]) + ' Used: ' + str(stats[1]))

            # Check for stale live games.
            cpy_live_games = self.games['live'].values()
            for game in cpy_live_games:
                # If a game in the live bucket hasn't been updated in a hour, then issue an alert.
                if (datetime.datetime.now(tz) - game.timestamp.replace(tzinfo=tz)).total_seconds() > 3600:
                    self.notify(f"WARNING: {game.id} hasnt been updated in over an hour")
                # If a game in the live bucket hasn't been updated in 5 hours, then drop it to the final bucket.
                if (datetime.datetime.now(tz) - game.timestamp.replace(tzinfo=tz)).total_seconds() > 5*3600:
                    self.notify(f"WARNING: {game.id} hasn't been updated in 5 hours.\nTransitioning from live to final.")
                    self.transition(game.id, 'live', 'final')

            # Determine wait time.
            # If we don't have a current game going, then wait for the next to start (or wait two hours).
            if not self.games['live']:
                wait_time = self.time_until_next_game(lines)
                wakeup_time = datetime.datetime.now(tz) + datetime.timedelta(seconds=wait_time)
                self.notify(f"""No live games, sleeping {wait_time} seconds.\nWakeup time at {wakeup_time.strftime('%Y-%m-%d %H:%M:%S')}""")
            # Else, pause for a minute, then continue scraping.
            else:
                wait_time = 60
            # Close the webpage while we sleep
            if wait_time > 60:
                webpage.close()
            # Sleep
            time.sleep(wait_time)
            # Reopen the webpage
            if wait_time > 60:
                webpage.open()
