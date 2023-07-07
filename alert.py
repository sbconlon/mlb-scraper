# This file defines the Alert class which sends SMS alerts to a given phone number.
#
# ALL CREDIT GOES TO: https://testingonprod.com/2021/10/24/how-to-send-text-messages-with-python-for-free/
#

import smtplib
import sys

class Alert:
    # email (str) - email to help send the SMS.
    # password (str) - note, this is the app password if using gmail.
    # phone_number (int or str) - phone number to send alerts to.
    # carrier (str) - identifier for phone carrier to use.
    def __init__(self, sender, password, reciever):
        self.auth = (sender, password)
        self.recipient = reciever
    
    def alert(self, message):
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(self.auth[0], self.auth[1])
            server.sendmail(self.auth[0], self.recipient, message)
        except:
            print("WARNING: Failed to send alert message.")

