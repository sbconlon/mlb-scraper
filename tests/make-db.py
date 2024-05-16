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
     db = mysql.connector.connect(host=config["db-host"],
                                  user=config["db-user"],
                                  password=config["db-password"])

     print('--> Connected to the database')
     print(db)
     print()

     # Get cursor
     cursor = db.cursor()

     # Make database
     db_name = 'testdb' if is_test else 'proddb'
     cursor.execute(f'DROP DATABASE {db_name}') # Drop the db if it already exits
     cursor.execute(f'CREATE DATABASE {db_name}')

     cursor.execute("SHOW DATABASES")

     print(f'--> Created the database, {db_name}')
     for x in cursor:
         print(x)
