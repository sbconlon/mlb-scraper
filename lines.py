# External imports
import datetime
import pandas as pd
import pytz
import requests
import sys
import yaml

# Internal imports
sys.path.insert(0, '../')
from game import GameState

class LineGenerator:
    default_params = {
                      'SPORT': 'baseball_mlb',
                      'REGIONS': 'us',                 # uk | us | eu | au.
                      'MARKETS': 'h2h,spreads,totals', # h2h | spreads | totals
                      'ODDS_FORMAT': 'decimal',        # decimal | american
                      'DATE_FORMAT': 'iso'             # iso | unix
                     }

    def __init__(self, keyfile, id_prefix_func, params=default_params):
        with open(keyfile, 'r') as yamlfile:
            self.key = yaml.load(yamlfile, Loader=yaml.FullLoader)['api-key']
        self.params = params
        self.remaining, self.used = -1, -1   # unkown at initialization time
        self.get_id_prefix = id_prefix_func

    tchar = lambda name, teams: 'A' if name == teams[0] else 'H'
    ochar = lambda name: 'O' if name == 'over' else 'U'

    to_eastern = lambda time: datetime.datetime.strptime(time, '%Y-%m-%dT%H:%M:%SZ'
                                          ).replace(tzinfo=pytz.utc
                                          ).astimezone(pytz.timezone('US/Eastern'))

    def process_moneyline(prefix, market, teams):
        assert(market['key'] == 'h2h')
        assert(len(market['outcomes']) == 2)
        lines = {}
        for outcome in market['outcomes']:
            assert(outcome['name'] in teams)
            lines[prefix+LineGenerator.tchar(outcome['name'], teams)+'_price'] = outcome['price']
        return lines

    def process_spread(prefix, market, teams):
        assert(market['key'] == 'spreads')
        assert(len(market['outcomes']) == 2)
        lines = {}
        for outcome in market['outcomes']:
            assert(outcome['name'] in teams)
            lines[prefix+LineGenerator.tchar(outcome['name'], teams)+'_price'] = outcome['price']
            lines[prefix+LineGenerator.tchar(outcome['name'], teams)+'_point'] = outcome['point']
        return lines

    def process_total(prefix, market):
        assert(market['key'] == 'totals')
        assert(len(market['outcomes']) == 2)
        lines = {}
        for outcome in market['outcomes']:
            assert(outcome['name'] in ('Over', 'Under'))
            lines[prefix+LineGenerator.ochar(outcome['name'])+'_price'] = outcome['price']
            lines[prefix+LineGenerator.ochar(outcome['name'])+'_point'] = outcome['point']
        return lines

    # Sends get request to the api
    # Returns raw response, unformatted.
    def query(self):
        # Send request to the api and get back a response
        response = requests.get(
                       f"https://api.the-odds-api.com/v4/sports/{self.params['SPORT']}/odds",
                       params={
                           'api_key': self.key,
                           'regions': self.params['REGIONS'],
                           'markets': self.params['MARKETS'],
                           'oddsFormat': self.params['ODDS_FORMAT'],
                           'dateFormat': self.params['DATE_FORMAT']
                       })
        # Update usage stats
        self.update_usage(response.headers['x-requests-remaining'],
                          response.headers['x-requests-used'])
        # Return raw response
        return response.json()


    # Takes raw response from the api and formats it.
    def format_response(self, response):
        games = {}
        for game in response:
            start = LineGenerator.to_eastern(game['commence_time'])
            teams = (game['away_team'], game['home_team'])
            id_prefix = self.get_id_prefix(teams[1], strt_time=start)
            line_info = {}
            for book in game['bookmakers']:
                bpre = book['key']+'_'
                line_info[bpre+'last'] = LineGenerator.to_eastern(book['last_update'])
                for market in book['markets']:
                    mpre = bpre + market['key']+'_'
                    line_info[mpre+'last'] = LineGenerator.to_eastern(market['last_update'])
                    if market['key'] == 'h2h':
                        line_info.update(LineGenerator.process_moneyline(mpre, market, teams))
                    if market['key'] == 'spreads':
                        line_info.update(LineGenerator.process_spread(mpre, market, teams))
                    if market['key'] == 'totals':
                        line_info.update(LineGenerator.process_total(mpre, market))
            games[id_prefix] = pd.Series(line_info)
        return games


    # Queries the api and returns the formatted response
    # Returns a dictionary game_id_prefix -> pd.series of line info
    def get(self):
        return self.format_response(self.query())

    # Returns usage stats
    def usage(self):
        return self.remaining, self.used

    # Updates usage stats
    def update_usage(self, remaining, used):
        self.remaining = int(remaining)
        self.used = int(used)
