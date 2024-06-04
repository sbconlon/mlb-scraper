import os
import datetime
from pathlib import Path
import pytz

class Logger:
    def __init__(self, outpath):
        # Make directories if it doesn't exit
        self.path = Path(outpath)
        self.path.parent.mkdir(exist_ok=True, parents=True)

    def log(self, txt=''):
        tz = pytz.timezone('US/Pacific')
        filepath = Path(os.path.join(self.path, datetime.datetime.now(tz).strftime('%Y%m%d') + '.txt'))
        with open(os.path.join(self.path, datetime.datetime.now(tz).strftime('%Y%m%d') + '.txt'), 'a') as file:
            file.write(txt + '\n')
