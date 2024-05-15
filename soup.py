import bs4 as bs
import datetime
import pytz
#from urllib.request import Request, urlopen
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
import time
from webdriver_manager.chrome import ChromeDriverManager

class Soup:

    url = 'https://www.mlb.com/scores'

    def __init__(self):
        # Raspberry Pi driver substitution
        #service = ChromeService(executable_path='/usr/bin/chromedriver') 
        #self.driver = webdriver.Chrome(service=service,
        #                               options=options)
        self.open()

    def brew(self):
        soup = bs.BeautifulSoup(self.driver.page_source, 'html.parser')
        return soup.find('main'
                        ).find('div', {'id': 'scores-schedule-root'}
                        ).find_all('div', {'data-test-mlb': 'singleGameContainer'})
    
    def open(self):
        options = webdriver.ChromeOptions()
        options.add_argument('log-level=3')
        options.add_argument('--headless')
        self.driver = webdriver.Chrome(ChromeDriverManager().install(),
                                       options=options)
        self.driver.implicitly_wait(5)
        self.driver.get(Soup.url)

    def close(self):
        self.driver.quit()
        self.driver = None


    """
    def brew():
        url = 'https://www.mlb.com/scores'
        req = Request(url , headers={'User-Agent': 'Mozilla/5.0'})
        webpage = urlopen(req).read()
        soup = bs.BeautifulSoup(webpage, "html.parser")
        return soup.find('main'
                        ).find('div', {'id': 'scores-schedule-root'}
                        ).find_all('div', {'data-test-mlb': 'singleGameContainer'})
    """

class SoupParser:
    def get_inning(soup):
        try:
            return soup.find('div', {'data-mlb-test': 'inningNumberLabel'}).text
        except:
            return ''

    def get_start_time_str(soup):
        try:
            return soup.find('div', {'data-mlb-test': 'gameStartTimesStateLabel'}).text
        except:
            return ''

    def get_final(soup):
        try:
            return soup.find('span', {'data-mlb-test': 'gameStartTimesStateLabel'}).text
        except:
            return ''

    def get_score(soup):
        try:
            boxscore = soup.find_all('table')[1]
            # Note: the 0th row of the table is the table header
            get_score = lambda row, col: int(boxscore.find_all('tr')[1+row].find_all('td')[col].find('div').get_text())
            away_score = get_score(0, 0) # away score is in the first row, first column of the boxscore
            home_score = get_score(1, 0) # home score is in the second row, first column of the boxscore
            return away_score, home_score
        except:
            return None

    # Outs are the second title in the game soup
    def get_outs(soup):
        try:
            outs = int(soup.find_all('title')[1].text[0])
            assert(outs <= 3 and outs >= 0)
            return outs
        except:
            return None

    def get_runners(soup):
        try:
            return [int(base['fill'] == '#EFB21F') for base in reversed(soup.find_all('rect'))]
        except:
            return [None, None, None]

    def get_count(soup):
        try:
            count_str = soup.find('div', {'class', 'inningStatestyle__StyledCountWrapper-sc-ywgvyn-2 hFpAXK'}).text
            return [int(x) for x in count_str.split(' - ')]
        except:
            return [None, None]

    def get_pitcher(soup):
        try:
            players = soup.find_all('div', {'data-mlb-test': 'playerNameLinks'})
            return players[0].text if len(players) == 2 else None
        except:
            return None

    def get_batter(soup):
        try:
            players = soup.find_all('div', {'data-mlb-test': 'playerNameLinks'})
            return players[1].text if len(players) == 2 else None
        except:
            return None

    def get_teams(soup):
        try:
            get_team = lambda idx: soup.find_all('div', {'data-mlb-test': 'teamNameLabel'})[idx].find_all('div')[0].text
            return (get_team(0), get_team(1))
        except:
            return (None, None)

    # Is warmup?
    def is_warmup(soup):
         return SoupParser.get_inning(soup) == 'Warmup'

    # Is the game yet to start?
    # Either the game has a valid start time
    # Or it is in the 'warmup' state.
    time_ptrn = re.compile(r'^\d?\d\:\d\d [AP]M ET')
    def is_pregame(soup):
        time = SoupParser.get_start_time_str(soup)
        return bool(SoupParser.time_ptrn.match(time))
    
    def get_start_time(soup):
        start_str = SoupParser.time_ptrn.match(
                        SoupParser.get_start_time_str(soup)    
                    ).group(0)
        eastern = pytz.timezone('US/Eastern')
        today = datetime.datetime.now().astimezone(eastern)
        start_time = datetime.datetime.strptime(start_str, "%I:%M %p ET")
        start_time.replace(year=today.year, month=today.month, day=today.day, tzinfo=eastern)
        return start_time

    # Checks if the given start time string is delayed.
    # Note: start_str should be the output from SoupParser.get_start_time_str().
    def is_delayed(soup):
        return 'Delayed Start' in SoupParser.get_start_time_str(soup)
    
    # Checks if a game is suspended.
    def is_suspended(soup):
        return 'Suspended' in SoupParser.get_start_time_str(soup)

    # Is the game for the soup live?
    # If the inning result has a valid prefix then the game is live.
    # This is meant to exclude the 'Warmup' status
    def is_live(soup):
        valid_innings = set(('Top', 'Bot', 'Mid', 'End'))
        inning = SoupParser.get_inning(soup)
        return inning[:3] in valid_innings and not SoupParser.is_suspended(soup)

    # Is the game for the soup final?
    def is_final(soup):
        final_ptrn = re.compile(r'Final')
        return bool(final_ptrn.match(SoupParser.get_final(soup)))
    
    def is_postponed(soup):
        postponed_ptrn = re.compile(r'Postponed')
        return bool(postponed_ptrn.match(SoupParser.get_final(soup)))

    # Set of pregame parsing functions
    pre_funcs = {
        'start_time': get_start_time_str,
        'teams':get_teams
    }

    # Set of live game parsing functions
    live_funcs = {
        'inning': get_inning,
        'score': get_score,
        'outs': get_outs,
        'runners': get_runners,
        'count': get_count,
        'pitcher': get_pitcher,
        'batter': get_batter,
        'teams':get_teams
    }

    # Set of post game parsing functions
    post_funcs = {
        'is_final': is_final,
        'score': get_score,
        'teams': get_teams
    }

    def parse_pre(soup):
        result = {}
        for key, f in SoupParser.pre_funcs.items():
            result[key] = f(soup)
        return result

    def parse_live(soup):
        result = {}
        for key, f in SoupParser.live_funcs.items():
            result[key] = f(soup)
        return result

    def parse_post(soup):
        result = {}
        for key, f in SoupParser.post_funcs.items():
            result[key] = f(soup)
        return result
