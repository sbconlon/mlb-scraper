import argparse
import yaml

from alert import Alert
from scraper import Scraper
from mysqldb import Database
from lines import LineGenerator
from csvdumper import CSVDumper

parser = argparse.ArgumentParser()
parser.add_argument('config')

args = parser.parse_args()

with open(args.config, 'r') as yamlfile:
    config = yaml.load(yamlfile, Loader=yaml.FullLoader)

# Initialize the alert system.
alerter = Alert(config["sender"],
                config["password"],
                config["reciever"])

# Connect to the MySQL DB, if enabled
dumper = Database(config["db-host"],
                  config["db-user"],
		  config["db-password"],
                  config["db-port"] if "db-port" in config else 3306) if config.get("db-enabled") else None

# Else, use the CSV Dumper
if not dumper:
    dumper = CSVDumper(config['game-outpath'], config['line-outpath'])

# Build line generator
line_generator = LineGenerator(config["api-key"])

# Start scrapper object, initializes games dictionary.
bot = Scraper(dumper, line_generator, alerter)

# Check for CSV paths if MySQL is not enabled
if not config.get("db-enabled"):
    assert('game-outpath' in config and 'line-outpath' in config)

# Run
while True:
#    try:
    if config.get("db-enabled"):
        bot.scrape(config["api-key"])
    else:
        bot.scrape(config["api-key"], game_outpath=config['game-outpath'], line_outpath=config['line-outpath'])
#    except Exception as e:
#        bot.notify("WARNING: Exception incountered, restarting scrape process.\n"+str(e))
