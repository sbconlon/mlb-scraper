# External imports
import argparse
import yaml

# Internal imports
from alert import Alert
from scraper import Scraper
from mysqldb import Database
from lines import LineGenerator
from csvdumper import CSVDumper
from logger import Logger

# Parse the command line args
parser = argparse.ArgumentParser()
parser.add_argument('config')

args = parser.parse_args()

# Open the configuration file
with open(args.config, 'r') as yamlfile:
    config = yaml.load(yamlfile, Loader=yaml.FullLoader)

# Initialize the alert system.
alerter = Alert(config["sender"],
                config["password"],
                config["reciever"])

# Initialize the logger
logger = Logger(config["log-path"])

# Connect to the MySQL DB, if enabled
dumper = Database(config["db-host"],
                  config["db-user"],
		  config["db-password"],
                  config["db-name"],
                  config["db-port"] if "db-port" in config else 3306) if config.get("db-enabled") else None

# Else, use the CSV Dumper
# Check for CSV paths if MySQL is not enabled
if not dumper:
    assert('game-outpath' in config and 'line-outpath' in config)
    dumper = CSVDumper(config['game-outpath'], config['line-outpath'])

# Build line generator
line_generator = LineGenerator(config["api-key"])

# Start scrapper object, initializes games dictionary.
bot = Scraper(dumper, line_generator, alerter, logger)

# Check for CSV paths if MySQL is not enabled
if not config.get("db-enabled"):
    assert('game-outpath' in config and 'line-outpath' in config)

# Run
while True:
#    try:
    bot.scrape()
#    except Exception as e:
#        bot.notify("WARNING: Exception incountered, restarting scrape process.\n"+str(e))
#        sleep(5*60)
