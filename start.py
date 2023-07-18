import argparse
import yaml

from alert import Alert
from scraper import Scraper

parser = argparse.ArgumentParser()
parser.add_argument('config')

args = parser.parse_args()

with open(args.config, 'r') as yamlfile:
    config = yaml.load(yamlfile, Loader=yaml.FullLoader)

# Initialize the alert system.
alerter = Alert(config["sender"],
                config["password"],
                config["reciever"])

# Start scrapper object, initializes games dictionary.
bot = Scraper(alerter)

# Run 
while True:
    try:
        bot.scrape(config['game-outpath'], config['line-outpath'], args.config)
    except Exception as e:
        bot.notify("WARNING: Exception incountered, restarting scrape process.\n"+str(e))
