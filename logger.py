import os
from datetime import date
from pathlib import Path

class Logger:
    def __init__(self, outpath):
        # Make directories if it doesn't exit
        self.path = Path(outpath)
        self.path.parent.mkdir(exist_ok=True, parents=True)

    def log(self, txt=''):
        filepath = Path(os.path.join(self.path, date.today().strftime('%Y%m%d') + '.txt'))
        with open(os.path.join(self.path, date.today().strftime('%Y%m%d') + '.txt'), 'a') as file:
            file.write(txt + '\n')
