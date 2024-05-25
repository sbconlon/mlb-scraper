import pandas as pd

from dumper import Dumper

import mysql.connector

class Database(Dumper):
    def __init__(self, host, user, password, db_name, port=3306):
        # Connect to the given MySQL database
        self.connection = mysql.connector.connect(host=host,
                                                  user=user,
                                                  password=password,
                                                  port=port,
                                                  database=db_name)
        # Log the connection
        print('--> Connected to the database:')
        print(self.connection)

    # MySQL command templates
    sql_insert_state_cmd = """
        INSERT INTO states
        (game_id, timestamp, inning, is_bot, outs, away, home, 1B,
         2B, 3B, batter, pitcher, balls, strikes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    sql_insert_h2h_cmd = """
        INSERT INTO h2h
        (game_id, bookmaker, timestamp, last, H_price, A_price)
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    sql_insert_spreads_cmd = """
        INSERT INTO spreads
        (game_id, bookmaker, timestamp, last, H_price, H_point, A_price, A_point)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    sql_insert_totals_cmd = """
        INSERT INTO totals
        (game_id, bookmaker, timestamp, last, U_price, U_point)
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    def dump_state(self, game):
       cursor = self.connection.cursor()
       val = (
         game.id,
         game.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
         game.inning,
         game.is_bot,
         game.outs,
         game.score[0],
         game.score[1],
         game.runners[0],
         game.runners[1],
         game.runners[2],
         game.batter,
         game.pitcher,
         game.count[0],
         game.count[1]
       )
       cursor.execute(Database.sql_insert_state_cmd, val)
       self.connection.commit()

    # Helper function for grouping columns by bet type
    def get_bet_type(name):
        bet_types = ('h2h', 'spreads', 'totals')
        for bt in bet_types:
            if bt in name:
                return bt
        return 'NA'


    def dump_lines(self, game):
       cursor = self.connection.cursor()
       for _, book_grp in game.line_info.groupby(lambda name: name.split('_')[0]): # Group cols by bookmaker
                for bet, bet_grp in book_grp.groupby(Database.get_bet_type): # Group bookmaker cols by bet type
                    if bet == 'NA':
                        continue
                    # Get bookmaker id
                    bookmaker = bet_grp.keys()[0].split('_'+bet)[0]
                    # Construct sql cmd and values depending on bet type
                    if bet == 'h2h':
                        cmd = Database.sql_insert_h2h_cmd
                        vals = (
                                     game.id,
                                     bookmaker,
                                     game.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                                     pd.to_datetime(game.line_info[bookmaker+'_h2h_last']).strftime('%Y-%m-%d %H:%M:%S'),
                                     game.line_info[bookmaker+'_h2h_H_price'],
                                     game.line_info[bookmaker+'_h2h_A_price']
                        )
                    elif bet == 'spreads':
                        cmd = Database.sql_insert_spreads_cmd
                        vals = (
                                     game.id,
                                     bookmaker,
                                     game.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                                     pd.to_datetime(game.line_info[bookmaker+'_spreads_last']).strftime('%Y-%m-%d %H:%M:%S'),
                                     game.line_info[bookmaker+'_spreads_H_price'],
                                     game.line_info[bookmaker+'_spreads_H_point'],
                                     game.line_info[bookmaker+'_spreads_A_price'],
                                     game.line_info[bookmaker+'_spreads_A_point']
                        )
                    elif bet == 'totals':
                        cmd = Database.sql_insert_totals_cmd
                        vals = (
                                     game.id,
                                     bookmaker,
                                     game.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                                     pd.to_datetime(game.line_info[bookmaker+'_totals_last']).strftime('%Y-%m-%d %H:%M:%S'),
                                     game.line_info[bookmaker+'_totals_U_price'],
                                     game.line_info[bookmaker+'_totals_U_point']
                        )
                    else:
                        continue
                # Exclude null values
                if bet_grp.isnull().values.any():
                    continue
                # Write out the values to the database
                cursor.execute(cmd, vals)
                self.connection.commit()
