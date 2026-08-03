import os
import json
from twilio.rest import Client
from dotenv import load_dotenv
import requests

load_dotenv()
account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
call_sid = "CAd56b9f64e7d34f8f5a9a80d289c15122"

url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls/{call_sid}/Events.json"
response = requests.get(url, auth=(account_sid, auth_token))
print(json.dumps(response.json(), indent=2))
