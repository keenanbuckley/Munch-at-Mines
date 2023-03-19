import json
import datetime
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import gspread
from oauth2client.service_account import ServiceAccountCredentials

import biteapi

# deals with setting up the gspread api client to be able to interact with the Google spreadsheets API
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

# Load hidden constants
CONFIG = load_config()
SODEXO_API_KEY = CONFIG["SODEXO_API_KEY"]
GOOGLE_CRED_FILE = CONFIG["GOOGLE_CRED_FILE"]
SPREADSHEET_NAME = CONFIG["SPREADSHEET_NAME"]
FROM_ADDRESS = CONFIG["FROM_ADDRESS"]
FROM_PASSWORD = CONFIG["FROM_PASSWORD"]

# Generates date string
date = datetime.date.today() + datetime.timedelta(days = 10)
date_string = biteapi.formatdate(date)

# Creates the json file
print('fetching data...')
json_file = biteapi.fetchdata(date_string, SODEXO_API_KEY)

print('formatting data...')
menu = biteapi.formatdata(date_string, json_file)

print('compiling html...')
output = biteapi.compilehtml(date, menu)

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
    day_name = ("Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")[date.weekday()]
    month_name = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")[date.month - 1]
    message['subject'] = day_name + ', ' + month_name + ' ' + date.day + ' at Mines Market'
    message['From'] = sender_email
    
    html_body = MIMEText(output, 'html')
    message.attach(html_body)
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_emails, message.as_string())

print('done.')