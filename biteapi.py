import datetime
import json
import requests
from pybars import Compiler
from premailer import transform

# MenuItem class holds data for individual menu items
class MenuItem:
    ''' holds data for individual menu items '''
    def __init__(self, item_name: str, item_description: str, item_ingredients: str, item_calories: int):
        self.name = item_name
        self.description = item_description
        self.item_ingredients = item_ingredients
        self.calories = item_calories

def formatdate(date: datetime.date) -> str:
    ''' convert datetime variable into string format for api requests '''
    year = str(date.year)
    month = str(date.month)
    day = str(date.day)

    while (len(month) < 2): month = "0" + month
    while (len(day) < 2): day = "0" + day

    date_string = "{}-{}-{}".format(year, month, day)
    return date_string

def fetchdata(date_string: str, apikey: str) -> dict:
    # Forulates API request
    headers = {'Ocp-Apim-Subscription-Key': apikey}
    url = 'https://bite-external-api.azure-api.net/extern/bite-application/location'
    payload = {'date': date_string, 'locationid': '75204001'}

    # Fetches menu in form of a json dict
    return json.loads(requests.get(url, params=payload, headers=headers).text)

def formatdata(date_string: str, json_file: dict) -> dict:
    # Date for searching json
    date = "{}T00:00:00".format(date_string)

    # Narrows down json to current date
    days = json_file["Menus"][0]["OrderDays"]

    unparsed_menu = None
    for d in days:
        if d["Date"] == date:
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
            except:
                pass
    
    return menu

def compilehtml(date: datetime.date, menu: dict) -> str:
    with open("menus.handlebars", "r") as template:
        compiler = Compiler()
        document = compiler.compile(template.read())
        templated = document({
            "day_name": ("Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")[date.weekday()],
            "month": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")[date.month - 1],
            "date": date.day,
            "menu": menu
        });
        return transform(templated, allow_loading_external_files=True)