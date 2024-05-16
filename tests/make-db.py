import argparse
import mysql.connector
import yaml

if __name__ == '__main__':
    # Define cli args
    parser = argparse.ArgumentParser(
                   prog='BuildDB',
                   description='Builds MySQL DB and tables')

    parser.add_argument('config')
    parser.add_argument('-p',
                        '--production',
                        action='store_true',
                        default=False)  # on/off flag
    # Parse args
    args = parser.parse_args()
    config_file = args.config
    is_test = not args.production

    # Read config file
    with open(args.config, 'r') as yamlfile:
        config = yaml.load(yamlfile, Loader=yaml.FullLoader)

    # Connect to the database server
    dbserver = mysql.connector.connect(host=config["db-host"],
                                       user=config["db-user"],
                                       password=config["db-password"])

    print('--> Connected to the database server')
    print(dbserver)
    print()

    # Get cursor
    cursor = dbserver.cursor()

    # Make database
    db_name = 'testdb' if is_test else 'proddb'
    cursor.execute(f'CREATE DATABASE {db_name}')

    cursor.execute("SHOW DATABASES")

    print(f'--> Created the database, {db_name}')
    for x in cursor:
        print(x)
    print()

    # Connect to the database
    db = mysql.connector.connect(host=config["db-host"],
                                 user=config["db-user"],
                                 password=config["db-password"],
                                 database=db_name)

    cursor = db.cursor()

    # Create tables
    cursor.execute(
    """
        CREATE TABLE states (id INT AUTO_INCREMENT PRIMARY KEY,
                             game_id VARCHAR(255),
                             timestamp DATETIME,
                             inning SMALLINT,
                             is_bot BOOLEAN,
                             outs SMALLINT,
                             away SMALLINT,
                             home SMALLINT,
                             1B BOOLEAN,
                             2B BOOLEAN,
                             3B BOOLEAN,
                             batter VARCHAR(255),
                             pitcher VARCHAR(225),
                             balls SMALLINT,
                             strikes SMALLINT)
    """)

    cursor.execute("SHOW TABLES")

    print('--> Created the tables')
    for x in cursor:
        print(x)
    print()
