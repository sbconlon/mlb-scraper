from dumper import Dumper

import mysql.connector

class Database(Dumper):
    def __init__(self, host, user, password, port=3306):
        # Connect to the given MySQL database
        self.connection = mysql.connector.connect(host=host,
                                                  user=user,
                                                  password=password,
                                                  port=port)
        # Log the connection
        print('--> Connected to the database:')
        print(self.connection)

    def dump_state(self, game):
        print('DUMP STATE')

    def dump_lines(self, game):
        print('DUMP LINES')
