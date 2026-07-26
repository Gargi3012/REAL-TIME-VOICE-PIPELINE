import os
import sys
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
client = Client(account_sid, auth_token)

calls = client.calls.list(limit=5)
for call in calls:
    print(f"Call SID: {call.sid} | Status: {call.status} | Duration: {call.duration}")
    notifications = client.api.v2010.accounts(account_sid).calls(call.sid).notifications.list(limit=5)
    for n in notifications:
        print(f"  -> Error {n.error_code}: {n.message_text}")
