from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
import json
import re

app = Flask(__name__)

# Setup Google Sheets API
SERVICE_ACCOUNT_JSON = os.environ.get('SERVICE_ACCOUNT_JSON')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SHEET_ID = '17mjosbO5z39dmwNvXUKnzh6a5zYn9nGJyA-Ez_9ZAGk'
SHEET_NAME = 'PIZZAPRICE'

if not SERVICE_ACCOUNT_JSON:
    raise Exception("SERVICE_ACCOUNT_JSON not found in environment variables")

creds_dict = json.loads(SERVICE_ACCOUNT_JSON)
creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

# Load item prices from sheet
result = sheet.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_NAME}!A2:B").execute()
data = result.get('values', [])
item_prices = {row[0].strip().lower(): float(row[1]) for row in data}

# Parsing functions
def parse_items(text):
    pattern = r'(\d+)\s+([\w\s\-]+?)(?:\sand\s|$)'
    matches = re.findall(pattern, text)
    return [(int(qty), name.strip().lower()) for qty, name in matches]

def parse_toppings(topping_text):
    topping_sets = {}
    patterns = re.findall(r'(.+?)\s+for\s+([\w\s\-]+?)(?:\sand\s|$)', topping_text)
    for toppings, pizza in patterns:
        topping_list = [t.strip().lower() for t in re.split(r'and|,', toppings)]
        topping_sets[pizza.strip().lower()] = topping_list
    return topping_sets

def extract_size_crust(pizza_name):
    description_parts = []

    # Detect size
    if "regular" in pizza_name:
        description_parts.append("Size : Regular")
    elif "medium" in pizza_name:
        description_parts.append("Size : Medium")
    elif "large" in pizza_name:
        description_parts.append("Size : Large")

    # Detect crust type
    if "cheese burst" in pizza_name:
        description_parts.append("Crust : Cheese Burst")
    elif "new hand tossed" in pizza_name:
        description_parts.append("Crust : New Hand Tossed")
    elif "classic hand tossed" in pizza_name:
        description_parts.append("Crust : Classic Hand Tossed")
    elif "wheat thin crust" in pizza_name:
        description_parts.append("Crust : Wheat Thin Crust")
    elif "fresh pan pizza" in pizza_name:
        description_parts.append("Crust : Fresh Pan Pizza")

    return " , ".join(description_parts)

@app.route('/')
def home():
    return "Pizza Price Calculator API is running!"

@app.route('/invoice_syntax', methods=['POST'])
def calculate_price():
    request_json = request.get_json()
    if not request_json:
        return jsonify({'error': 'Invalid JSON'}), 400

    pizzaname = request_json.get('pizzaname', '')
    pizzatoppings = request_json.get('pizzatoppings', '')
    additionalitems = request_json.get('additionalitems', '')

    parsed_pizzas = parse_items(pizzaname)
    parsed_toppings = parse_toppings(pizzatoppings)
    result = []

    # Process pizzas
    for qty, pizza in parsed_pizzas:
        base_price = item_prices.get(pizza, 0)
        topping_list = []

        # Match toppings to pizza by inclusion
        for top_pizza_key in parsed_toppings:
            if top_pizza_key in pizza:
                topping_list = parsed_toppings[top_pizza_key]
                break

        # Calculate topping prices individually
        topping_price_details = []
        topping_total = 0
        for t in topping_list:
            t_price = item_prices.get(t, 0)
            topping_total += t_price
            topping_price_details.append(f"{t}({t_price})")

        total_price = base_price + topping_total

        description = f"Base Price({base_price})"
        size_crust_desc = extract_size_crust(pizza)
        if size_crust_desc:
            description += f" , {size_crust_desc}"
        if topping_price_details:
            description += f" , Toppings : {', '.join(topping_price_details).title()}"

        result.append({
            'name': pizza,
            'currency': 'USD',
            'amount': total_price,
            'qty': qty,
            'description': description
        })

    # Process additional items
    parsed_additional = parse_items(additionalitems)
    for qty, item in parsed_additional:
        item_price = item_prices.get(item, 0)
        result.append({
            'name': item,
            'currency': 'USD',
            'amount': item_price,
            'qty': qty
        })

    return jsonify(result)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
