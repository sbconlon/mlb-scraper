# External imports
import datetime
import pytz
import time

# Internal imports
from soup import Soup, SoupParser
from game import GameState
from lines import LineGenerator


class Scrapper:

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

    def __init__(self, alerter):
        # Issue alerts
        self.alerter = alerter
        # Game states
        # Games should transition from: pregame -> live -> final
        # They can not go backward.
        self.games = {
                        'pregame': {},
                        'live': {},
                        'final': {}
                     }

    # This function prints the given message to the console
    # and issues an alert.
    def notify(self, message):
        print(message)
        self.alerter.alert(message)

    # The lookup functions take a game prefix and match it to a game in the
    # games dictionary, or constructs a new game if a match is not found.
    #
    # Returns the GameState for the given prefix.

    # Looks up prefix in a given games dictionary
    def match(self, state, prefix):
        return [id for id in self.games[state].keys() if id[:-1] == prefix]

    # Lookup live games that match the prefix.
    def lookup_live(self, prefix):
        # First, check if the prefix matches a game in the live game hash.
        live_matches = self.match('live', prefix)
        if live_matches:
            # If we have a match then return the GameState.
            assert(len(live_matches) == 1) # Assumption 3
            return self.games['live'][live_matches[0]]
        # Second check if the prefix matches a game in the pregame hash.
        pregame_matches = self.match('pregame', prefix)
        if pregame_matches:
            # If we have multiple matches then take the game with the earliest
            # start time.
            return sorted([self.games['pregame'][id] for id in pregame_matches],
                           key=lambda g: g.start_time)[0]
        # Else, we need to create a new game
        id = GameState.new_game_id(prefix)
        self.notify(f'CREATING NEW LIVE GAME {id}')
        self.games['live'][id] = GameState(id)
        return self.games['live'][id]

    # Lookup games in the pregame hash.
    def lookup_pregames(self, prefix, start):
        # Check for prefix matches in the pregame hash.
        pregame_matches = self.match('pregame', prefix)
        # If we have matches, then return the one with the matching start time.
        candidate = [id for id in pregame_matches
                        if self.games['pregame'][id].start_time == start]
        assert(len(candidate) <= 1) # Match should be unique (or zero).
        if candidate:
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
        # We can multiple matches here if both games of a double header have
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
        assert((orig, dest) in Scrapper.allowed_txn)
        # Check that a game with the same id isn't in our destination state.
        assert(not id in self.games[dest].keys())
        # Move the game
        self.games[dest][id] = self.games[orig][id]
        del self.games[orig][id]

    # Returns the time until the next game starts in seconds.
    def time_until_next_game(self, lines):
        # Get the current time, in eastern timezone.
        nowtime = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
        # Get the next game start time, in eastern timezone, filtered s.t. we exclude games
        # that have already started.
        gametime = min([gtime for gtime in [to_eastern(game['commence_time']) for 
                                            game in odds_response.json()] if gtime > nowtime])
        # Calculate the difference in seconds.
        secs = (gametime - nowtime).total_seconds()
        # Assert that we don't have a negative time.
        if secs < 0:
            message = f"""Invalid next game time, nowtime={
                              nowtime.strftime('%Y-%m-%d %H:%M:%S')} gametime={
                              gametime.strftime('%Y-%m-%d %H:%M:%S')}"""
            self.notify(message)
            raise Exception(message)
        return secs

    def scrap(self, game_outpath, line_outpath, keyfile):
        webpage = Soup()
        linegen = LineGenerator(keyfile, GameState.get_id_prefix)
        while True:
            print(f"---> {datetime.date.today()} {datetime.datetime.now().strftime('%H:%M:%S')}")
            
            # Time the soup was brewed and lines were generated.
            timestamp = datetime.datetime.now()
            # Get current lines.
            lines = linegen.get()
            
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
                                lines.get(prefix, None))
                    # Dump game state and line info
                    game.dump_state(game_outpath)
                    if not game.line_info is None:
                        game.dump_lines(line_outpath)
                    # Log
                    print('---------------------------------------------------')
                    print(game)
                    print()
                #
                # Parse pre game info
                elif SoupParser.is_pregame(soup):
                    # Find the GameState for the corresponding prefix
                    start_time = SoupParser.get_start_time(soup)
                    game = self.lookup_pregames(prefix, start_time)
                    # Set start time if its not already set.
                    if not game.start_time:
                        game.start_time = start_time
                #
                # Parse post game info
                elif SoupParser.is_final(soup):
                    # Find the GameState for the corresponding prefix
                    game = self.lookup_final(prefix)
                    # Move the game to the final hash, if needed.
                    if game.id in self.games['pregame'].keys():
                        self.notify(f'TRANSITIONING {game.id} from pregame to final')
                        self.transition(game.id, 'pregame', 'final')
                    elif game.id in self.games['live'].keys():
                        self.notify(f'TRANSITIONING {game.id} from live to final')
                        self.transition(game.id, 'live', 'final')
                else:
                    self.notify('WARNING: Couldnt identify the game soup.')
                    self.notify(SoupParser.parse_live(soup))
            
            # Print line API usage statistics
            stats = linegen.usage()
            print('Remaining:', stats[0], ' Used:', stats[1])

            # Check for stale live games.
            for game in self.games['live'].values(): 
                # If a game in the live bucket hasn't been updated in a hour, then issue an alert.
                if (datetime.datetime.now() - game.timestamp).total_seconds() > 3600:
                    self.notify(f"WARNING: {game.id} hasnt been updated in over an hour")
                # If a game in the live bucket hasn't been updated in 5 hours, then drop it to the final bucket.
                if (datetime.datetime.now() - game.timestamp).total_seconds() > 5*3600:
                    self.notify(f"""WARNING: {game.id} hasn't been updated in 5 hours.
                                       Transitioning it from live to final.""")
                    self.transition(game.id, 'live', 'final')
            
            # Determine wait time.
            # If we don't have a current game going, then wait for the next to start or wait two hours.
            if not self.games['live']:
                wait_time = min(self.time_until_next_game(lines), 2*60*60)
                wakeup_time = datetime.datetime.now() + datetime.timedelta(seconds=wait_time)
                self.notify(f"""No live games, sleeping {wait_time} seconds. 
                                Wakeup time at {wakeup_time.strftime('%Y-%m-%d %H:%M:%S')}""")
            # Else, pause for a minute, then continue scraping.
            else:
                wait_time = 60
            # Sleep
            time.sleep(wait_time)
