import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
client = Client(os.environ['TWILIO_ACCOUNT_SID'], os.environ['TWILIO_AUTH_TOKEN'])

notifications = client.notifications.list(limit=5)
print("RECENT ACCOUNT NOTIFICATIONS:")
for n in notifications:
    print(f"[{n.message_date}] Call SID: {n.call_sid} | Error: {n.error_code} | Msg: {n.message_text}")
    print(f"URL: {n.request_url}")
