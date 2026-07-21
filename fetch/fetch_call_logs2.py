import os
from twilio.rest import Client
from dotenv import load_dotenv
import pprint

load_dotenv()
client = Client(os.environ['TWILIO_ACCOUNT_SID'], os.environ['TWILIO_AUTH_TOKEN'])
sid = 'CAcc48ad786717085634eddcf9c1733ee0'
call = client.calls(sid).fetch()

call_dict = call.__dict__
# Remove auth tokens or client objects if present
safe_dict = {k: v for k, v in call_dict.items() if not k.startswith('_')}
pprint.pprint(safe_dict)
