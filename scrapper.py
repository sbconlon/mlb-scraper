# External imports
import datetime
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

    def __init__(self):
        # Game states
        # Games should transition from: pregame -> live -> final
        # They can not go backward.
        self.games = {
                        'pregame': {},
                        'live': {},
                        'final': {}
                     }

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
        print(f'CREATING NEW LIVE GAME {id}')
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
        print(f'CREATING NEW PREGAME {id}')
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
        print(f'CREATING NEW FINAL GAME {id}')
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
                        print(f'TRANSITIONING {game.id} from pregame to live')
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
                    # Set start time if its not already.
                    if not game.start_time:
                        game.start_time = start_time
                #
                # Parse post game info
                elif SoupParser.is_final(soup):
                    # Find the GameState for the corresponding prefix
                    game = self.lookup_final(prefix)
                    # Move the game to the final hash, if needed.
                    if game.id in self.games['pregame'].keys():
                        print(f'TRANSITIONING {game.id} from pregame to final')
                        self.transition(game.id, 'pregame', 'final')
                    elif game.id in self.games['live'].keys():
                        print(f'TRANSITIONING {game.id} from live to final')
                        self.transition(game.id, 'live', 'final')
                else:
                    print('WARNING: Couldnt identify the game soup.')
                    print(SoupParser.parse_live(soup))

            #print()
            #print(f"Pre  game count: {len(self.games['pregame'])}")
            #for pre_id in self.games['pregame'].keys():
            #    print(pre_id)
            #print(f"Live game count: {len(self.games['live'])}")
            #for liv_id in self.games['live'].keys():
            #    print(liv_id)
            #print(f"Post game count: {len(self.games['final'])}")
            #for fin_id in self.games['final'].keys():
            #    print(fin_id)
            #print()
            stats = linegen.usage()
            print('Remaining:', stats[0], ' Used:', stats[1])
            time.sleep(60) # wait for 2.5 mins, approx. avg. at-bat length
