import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()
client = Client(os.environ['TWILIO_ACCOUNT_SID'], os.environ['TWILIO_AUTH_TOKEN'])
sid = 'CAcc48ad786717085634eddcf9c1733ee0'
call = client.calls(sid).fetch()

print(f"Call Status: {call.status}")
print(f"Call Duration: {call.duration}")
print(f"Call Answered By: {getattr(call, 'answered_by', 'N/A')}")
print(f"Call End Time: {call.end_time}")
