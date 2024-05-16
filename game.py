import datetime
import pandas as pd
import os


class GameState:
    # This is necessary for tracking double headers
    prefix_ids = {} # game prefix, 'home team id' + 'date' -> frequency

    # Load dataframe of team info
    teams_df = pd.read_csv('./data/TEAM2022', header=None)
    teams_df.columns = ['id', 'league', 'city', 'name']

    # Home team name to Retrosheets team id
    def get_team_id(name):
        words = name.split(' ')
        for i in range(1, len(words)+1):
            phrase = ''
            for word in words[len(words)-i:]:
                phrase += word
                phrase += ' '
            phrase = phrase [:-1] # remove trailing space
            try:
                return GameState.teams_df.loc[
                        GameState.teams_df['name'] == phrase]['id'].to_numpy()[0]
            except:
                pass
        print(f'ERROR: Couldnt find {name} in ./data/TEAM2022 list.')
        assert(False)

    # Get game id prefix.
    # Prefix = home team id + date
    def get_id_prefix(name, strt_time=None):
        strt_time = datetime.date.today() if strt_time == None else strt_time
        return GameState.get_team_id(name) + strt_time.strftime('%Y%m%d')

    # Make a game id for a new game, given the prefix.
    def new_game_id(prefix):
        # Get suffix by checking prefix_ids for duplicate prefixes
        if prefix in GameState.prefix_ids:
            suffix = str(GameState.prefix_ids[prefix])
            GameState.prefix_ids[prefix] += 1
        else:
            suffix = '0'
            GameState.prefix_ids[prefix] = 1
        return prefix + suffix


    def __init__(self, id, dump_to_sql=False):
        # Id
        self.id = id
        self.date = datetime.date.today()
        self.teams = ['', ''] # away, home
        self.start_time = None
        self.is_final = None
        # State features
        self.timestamp = None
        self.inning = None
        self.is_bot = None
        self.outs = None
        self.score = [0, 0]
        self.runners = [False, False, False]
        self.batter = ''
        self.pitcher = ''
        self.count = (None, None)
        # Line information
        self.line_info = None
        # Write to a MySQL DB (to CSV if not enabled)
        self.enable_sql = dump_to_sql

    def update(self, timestamp, new_state, new_lines):
        self.timestamp = timestamp
        self.line_info = new_lines
        if not self.line_info is None:
            self.line_info['timestamp'] = timestamp
        # 'Top #', 'Bot #', 'Mid #', 'End #'
        self.inning = int(new_state['inning'][4:])
        self.is_bot = int(new_state['inning'][:3] == 'Bot' or
                          new_state['inning'][:3] == 'Mid' or
                          new_state['inning'][:3] == 'End')
        self.outs = new_state['outs'] % 3
        self.score = new_state['score']
        self.runners = new_state['runners']
        self.batter = new_state['batter']
        self.pitcher = new_state['pitcher']
        self.count = new_state['count']

    def dump_to_sql(self, db_cursor, rtype, row):
        assert(rtype in ('state', 'lines'))

    def dump_to_csv(self, path, row):
        filename = path+f'/{self.id}.csv'
        if os.path.exists(filename):
            df = pd.read_csv(filename)
            df = pd.concat([df, row.to_frame().T], ignore_index=True)
            df.to_csv(filename, index=False)
        else:
            row.to_frame().T.to_csv(filename, index=False)

    def dump(self, *argv):
        self.dump_to_sql(argv[0], argv[1], argv[2]) if self.enable_sql else self.dump_to_csv(argv[0], argv[1])

    def dump_state(self, path):
        row = pd.Series({'timestamp': self.timestamp,
                         'inning':    self.inning,
                         'is_bot':    self.is_bot,
                         'outs':      self.outs,
                         'away':      self.score[0],
                         'home':      self.score[1],
                         '1B':        int(self.runners[0]),
                         '2B':        int(self.runners[1]),
                         '3B':        int(self.runners[2]),
                         'batter':    self.batter,
                         'pitcher':   self.pitcher,
                         'balls':     self.count[0],
                         'strikes':   self.count[1]})
        self.dump(path, row)

    def dump_lines(self, path):
        self.dump(path, self.line_info)

    def __str__(self):
        # Build game state string
        inning_str = 'Bot' if self.is_bot else 'Top'
        state_str =  f"{self.id}   {str(self.timestamp)}\n"
        state_str += f"\n"
        state_str += f"{inning_str} {self.inning}\n"
        state_str += f"Home: {self.score[1]} Away: {self.score[0]}\n"
        state_str += f"Outs: {self.outs}\n"
        state_str += f"\n"
        state_str += f"Pitcher: " + str(self.pitcher) + "\n"
        state_str += f"\n"
        state_str += f"Batter: " + str(self.batter) + "\n"
        state_str += f"\n"
        state_str += f"Count: {self.count[0]}-{self.count[1]}\n"
        state_str += f"\n"
        state_str += f"  {'o' if self.runners[1] else '.'}\n"
        state_str += f"{'o' if self.runners[2] else '.'} - {'o' if self.runners[0] else '.'}\n"
        state_str += f"  .\n"
        state_str += f"\n"
        if not self.line_info is None:
            state_str += str(self.line_info.filter(regex='fanduel'))
        return state_str
