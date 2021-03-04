import json
import datetime
from logging import FileHandler, Logger, LoggerAdapter, StreamHandler
import logging
from typing import Union
import backoff
from backoff import on_exception, expo
import requests
import os

from requests.api import request
from requests.models import Response
from pybars import Compiler
from premailer import transform
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# deals with setting up the gspread api client to be able to interact with
# the Google spreadsheets API


def client(cred_file_path):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        cred_file_path, scope
    )
    gc = gspread.authorize(credentials)
    return gc

# takes the authorized client and the name of the spreadsheet
# returns a gspread sheet object


def spreadsheet(client, name):
    return client.open(name)

# Returns a pair of the email and sign-up/sign-out option selected on form


def emails(worksheet):
    for row in worksheet.get_all_records():
        if row["Email Address"]:
            yield (row["Email Address"], row["Receive nightly emails that notify you about the next day's meals?"])

# Pulls hidden constants from a main_config.json file


def load_config():
    with open("main_config.json", "r") as fp:
        return json.load(fp)

# MenuItem class holds data for individual menu items


class MenuItem:
    def __init__(self, item_name: str, item_description: str,
                 item_ingredients: str, item_calories: int):
        self.name = item_name
        self.description = item_description
        self.item_ingredients = item_ingredients
        self.calories = item_calories


# Load hidden constants
CONFIG = load_config()
SODEXO_API_KEY = CONFIG["SODEXO_API_KEY"]
GOOGLE_CRED_FILE = CONFIG["GOOGLE_CRED_FILE"]
SPREADSHEET_NAME = CONFIG["SPREADSHEET_NAME"]
FROM_ADDRESS = CONFIG["FROM_ADDRESS"]
FROM_PASSWORD = CONFIG["FROM_PASSWORD"]

# Generates date string
date = datetime.date.today() + datetime.timedelta(days=1)
year = str(date.year)
month_index = date.month
month = str(month_index)
day = str(date.day)

while (len(month) < 2):
    month = "0" + month
while (len(day) < 2):
    day = "0" + day

date_string = "{}-{}-{}".format(year, month, day)


# Forulates API request
requestDate = date_string
headers = {'Ocp-Apim-Subscription-Key': SODEXO_API_KEY}
url = 'https://bite-external-api.azure-api.net/extern/bite-application/location'
payload = {'date': requestDate, 'locationid': '75204001'}


# implement backoff
def lookup_max_backoff_time() -> int:
    # TODO set backoff parameters through global config
    return 60 * 60

# logging notes:
#   - TODO set up cohesive logging across entire script
#   - backoff uses the logger named 'backoff' be default
#   - for logging granularoity between backoffs and failures, implement
#       logging callbacks instead (on_backoff, etc)
logging.getLogger('backoff').addHandler(FileHandler('backoff.log'))


def http_client_error(e: requests.RequestException) -> bool:
    """Determine if the RequestException failed due to a 400-level
    (client error) request.

    Args:
        e (requests.RequestException): Exception returned by an HTTP request.

    Returns:
        bool: RequestException was caused by client error.
    """
    return 400 <= e.response.status_code < 500


@backoff.on_exception(
    backoff.expo,
    requests.RequestException,
    max_time=lookup_max_backoff_time,
    giveup=http_client_error
) # Loses docstring, library does not use functools.wraps()
def requests_get_backoff(self, url, params=None, **kwargs) -> requests.Response:
    """Performs a requests.get() call with exponential backoff.

    Backoff will give up if the time has exceeded lookup_max_backoff_time or the
    status code is a 400-level (client error).

    Args:
        url (str): URL to send.
        params (iterable, optional): Dictionary, list of tuples, or bytes to send
        in the query string. Defaults to None.

    Returns:
        requests.Response: Response to HTTP GET request.
    """
    return requests.get(url, params=params, **kwargs)


# Creates the json file
print('fetching data...')
json_file = json.loads(
    requests_get_backoff(
        url,
        params=payload,
        headers=headers).text)


print('reorganizing data...')
# Date for searching json
date_string = "{}T00:00:00".format(date_string)

# Narrows down json to current date
days = json_file["Menus"][0]["MenuDays"]

unparsed_menu = None
for d in days:
    if d["Date"] == date_string:
        unparsed_menu = d["MenuItems"]
        break

menu: dict = {}
for item in unparsed_menu:
    item_name = item["FormalName"]
    if item_name != "":
        try:
            item_meal = item["Meal"]
            item_location = item["Course"]
            item_description = item["Description"]
            item_ingredients = item["Ingredients"]
            item_calories = int(item["Calories"])

            if item_meal not in menu.keys():
                menu[item_meal] = {}

            if item_location not in menu[item_meal].keys():
                menu[item_meal][item_location] = []

            menu[item_meal][item_location].append(MenuItem(
                item_name,
                item_description,
                item_ingredients,
                item_calories
            ).__dict__)
        except BaseException:
            pass

print('compiling data...')
output = None
with open("menus.handlebars", "r") as template:
    compiler = Compiler()
    document = compiler.compile(template.read())
    templated = document({
        "day_name": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[date.weekday()],
        "month": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")[month_index - 1],
        "date": day,
        "menu": menu
    })
    output = transform(templated)

# Write to file for testing
with open("output.html", "w") as html:
    html.write(output)


# Prepare and send email to self
print('sending email...')
port = 465  # For SSL
smtp_server = "smtp.gmail.com"
sender_email = FROM_ADDRESS
password = FROM_PASSWORD

# Prepare list of receivers from online spreadsheet
google_client = client(GOOGLE_CRED_FILE)
spreadsheet = spreadsheet(google_client, SPREADSHEET_NAME)
worksheet = spreadsheet.sheet1
entries = list(emails(worksheet))
receiver_emails = []
for entry in entries:
    if entry[1] == 'Yes':
        receiver_emails.append(entry[0])

# Send message
if receiver_emails:
    message = MIMEMultipart('alternative')
    day_name = (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday")[
        date.weekday()]
    month_name = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December")[
        month_index -
        1]
    message['subject'] = day_name + ', ' + \
        month_name + ' ' + day + ' at Mines Market'
    message['From'] = sender_email

    html_body = MIMEText(output, 'html')
    message.attach(html_body)
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_emails, message.as_string())

print('done.')
