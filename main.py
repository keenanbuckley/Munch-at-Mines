import json
import datetime
import requests
import os

# MenuItem class holds data for individual menu items
class MenuItem:
    def __init__(self, item_name: str, item_description: str, item_ingredients: str, item_calories: int):
        self.name = item_name
        self.description = item_description
        self.item_ingredients = item_ingredients
        self.calories = item_calories

# Pulls API key from local environment
SODEXO_API_KEY = os.environ["SODEXO_API_KEY"]

# Generates date string
date = datetime.date.today()
year = str(date.year)
month = str(date.month)
day = str(date.day)

while (len(month) < 2): month = "0" + month
while (len(day) < 2): month = "0" + day

date_string = "{}-{}-{}".format(year, month, day)


# Forulates API request
requestDate = date_string
headers = {'Ocp-Apim-Subscription-Key': SODEXO_API_KEY}
url = 'https://bite-external-api.azure-api.net/extern/bite-application/location'
payload = {'date': requestDate, 'locationid': '75204001'}


# Creates the json file
json_file = json.loads(requests.get(url, params=payload, headers=headers).text)


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
        except:
            pass

with open("test.json", "w") as file:
    file.write(json.dumps(menu))
