from dumper import Dumper

class CSVDumper(Dumper):
    def __init__(self, state_outpath, lines_outpath):
        self.state_outpath = state_outpath
        self.lines_outpath = lines_outpath

    # Dump the row to the csv at the given filename
    # Create the csv file if one does not exist
    def dump(self, filename, row):
        if os.path.exists(filename):
            df = pd.read_csv(filename)
            df = pd.concat([df, row.to_frame().T], ignore_index=True)
            df.to_csv(filename, index=False)
        else:
            row.to_frame().T.to_csv(filename, index=False)

    # Build state row and write it out to the game csv at the
    # state output path.
    def dump_state(self, game):
        row = pd.Series({'timestamp': game.timestamp,
                         'inning':    game.inning,
                         'is_bot':    game.is_bot,
                         'outs':      game.outs,
                         'away':      game.score[0],
                         'home':      game.score[1],
                         '1B':        int(game.runners[0]),
                         '2B':        int(game.runners[1]),
                         '3B':        int(game.runners[2]),
                         'batter':    game.batter,
                         'pitcher':   game.pitcher,
                         'balls':     game.count[0],
                         'strikes':   game.count[1]})

        self.dump(self.state_outpath+f'/{game.id}.csv', row)

    # Build lines row and write it out to the game csv at the
    # lines output path.
    def dump_lines(self, game):
        self.dump(self.lines_outpath+f'/{game.id}.csv', game.line_info)
