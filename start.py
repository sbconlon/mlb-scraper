import argparse
import yaml

from scrapper import Scrapper

parser = argparse.ArgumentParser()
parser.add_argument('config')

args = parser.parse_args()

with open(args.config, 'r') as yamlfile:
    config = yaml.load(yamlfile, Loader=yaml.FullLoader)

bot = Scrapper()
bot.scrap(config['game-outpath'], config['line-outpath'], args.config)
