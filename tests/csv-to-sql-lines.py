import argparse
import mysql.connector
import os
import pandas as pd
import yaml

if __name__ == '__main__':
    # Define cli args
    parser = argparse.ArgumentParser(
                   prog='BuildDB',
                   description='Builds MySQL DB and tables')

    parser.add_argument('config')

    parser.add_argument('path')

    parser.add_argument('-p',
                        '--production',
                        action='store_true',
                        default=False)  # on/off flag

    # Parse args
    args = parser.parse_args()
    is_test = not args.production

    # Read config file
    with open(args.config, 'r') as yamlfile:
        config = yaml.load(yamlfile, Loader=yaml.FullLoader)

    # Connect to the database server
    db_name = 'testdb' if is_test else 'proddb'
    db = mysql.connector.connect(host=config["db-host"],
                                 user=config["db-user"],
                                 password=config["db-password"],
                                 database=db_name)
    cursor = db.cursor()

    print('--> Connected to the database')
    print(db)
    print()

    # SQL INSERT command templates
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

    # Helper function for grouping columns by bet type
    def get_bet_type(name):
        bet_types = ('h2h', 'spreads', 'totals')
        for bt in bet_types:
            if bt in name:
                return bt
        return 'NA'

    # Read data from input directory path
    total_rows = 0
    for file in os.listdir(os.fsencode(args.path)):
        filename = os.fsdecode(file)
        if filename.endswith('.csv'):
            game_id = filename[:-4]
            df = pd.read_csv(args.path+'/'+filename, parse_dates=['timestamp'])
            for _, book_grp in df.columns.to_series().groupby(lambda name: name.split('_')[0]): # Group cols by bookmaker
                for bet, bet_grp in book_grp.groupby(get_bet_type): # Group bookmaker cols by bet type
                    bookmaker = bet_grp.to_list()[0].split('_'+bet)[0]
                    if bet == 'h2h':
                        cmd = sql_insert_h2h_cmd
                        vals = [
                                   (
                                     game_id,
                                     bookmaker,
                                     row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                                     pd.to_datetime(row[bookmaker+'_h2h_last']).strftime('%Y-%m-%d %H:%M:%S'),
                                     row[bookmaker+'_h2h_H_price'],
                                     row[bookmaker+'_h2h_A_price']
                                   )
                                 for _, row
                                 in df[['timestamp']+bet_grp.to_list()].iterrows()
                                 if not row.isnull().values.any()
                        ]
                    elif bet == 'spreads':
                        cmd = sql_insert_spreads_cmd
                        vals = [
                                   (
                                     game_id,
                                     bookmaker,
                                     row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                                     pd.to_datetime(row[bookmaker+'_spreads_last']).strftime('%Y-%m-%d %H:%M:%S'),
                                     row[bookmaker+'_spreads_H_price'],
                                     row[bookmaker+'_spreads_H_point'],
                                     row[bookmaker+'_spreads_A_price'],
                                     row[bookmaker+'_spreads_A_point']
                                   )
                                 for _, row
                                 in df[['timestamp']+bet_grp.to_list()].iterrows()
                                 if not row.isnull().values.any()
                        ]
                    elif bet == 'totals':
                        cmd = sql_insert_totals_cmd
                        vals = [
                                   (
                                     game_id,
                                     bookmaker,
                                     row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                                     pd.to_datetime(row[bookmaker+'_totals_last']).strftime('%Y-%m-%d %H:%M:%S'),
                                     row[bookmaker+'_totals_U_price'],
                                     row[bookmaker+'_totals_U_point']
                                   )
                                 for _, row
                                 in df[['timestamp']+bet_grp.to_list()].iterrows()
                                 if not row.isnull().values.any()
                        ]
                    else:
                        continue
                # Write out the values to the database
                cursor.executemany(cmd, vals)
                total_rows += cursor.rowcount

    print('--> Total rows written:', total_rows)
    print()
