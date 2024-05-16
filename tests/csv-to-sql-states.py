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

    # SQL INSERT command template
    sql_insert_cmd = """
        INSERT INTO states
        (game_id,
         timestamp,
         inning,
         is_bot,
         outs,
         away,
         home,
         1B,
         2B,
         3B,
         batter,
         pitcher,
         balls,
         strikes)
        VALUES (%s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s)
    """

    # Read data from input directory path
    total_rows = 0
    for file in os.listdir(os.fsencode(args.path)):
        filename = os.fsdecode(file)
        if filename.endswith('.csv'):
            df = pd.read_csv(args.path+'/'+filename, parse_dates=["timestamp"])
            game_id = filename[:-4]
            vals = [(game_id,
                     row["timestamp"].strftime('%Y-%m-%d %H:%M:%S'),
                     int(row["inning"]),
                     bool(row["is_bot"]),
                     int(row["outs"]),
                     int(row["away"]),
                     int(row["home"]),
                     bool(row["1B"]),
                     bool(row["2B"]),
                     bool(row["3B"]),
                     str(row["batter"]),
                     str(row["pitcher"]),
                     int(row["balls"]),
                     int(row["strikes"])) for _, row in df.iterrows()]

            cursor.executemany(sql_insert_cmd, vals)
            total_rows += cursor.rowcount

    print('--> Total rows written:', total_rows)
    print()
