import argparse
import mysql.connector
import yaml

if __name__ == '__main__':
     # Define cli args
     parser = argparse.ArgumentParser(
                    prog='DropDB',
                    description='Drops the given MySQL DB and tables')

     parser.add_argument('config')
     parser.add_argument('dbname')

     # Parse args
     args = parser.parse_args()

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
     assert(args.dbname)
     cursor.execute(f'DROP DATABASE {args.dbname}') # Drop the db if it already exits

     cursor.execute("SHOW DATABASES")

     print(f'--> Dropped the database, {args.dbname}')
     for x in cursor:
         print(x)
     print()
