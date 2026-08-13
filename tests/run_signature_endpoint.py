import asyncio
from fastapi.testclient import TestClient
from app.main import app
from twilio.request_validator import RequestValidator
import os
from dotenv import load_dotenv

load_dotenv()
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
validator = RequestValidator(auth_token)
url = "http://testserver/inbound-call"
post_vars = {'To': '+917082968702', 'From': '+18303546921', 'CallSid': 'CA123'}

signature = validator.compute_signature(url, post_vars)
print(f"Computed Signature: {signature}")

client = TestClient(app)
try:
    response = client.post(
        "/inbound-call", 
        data=post_vars,
        headers={"X-Twilio-Signature": signature, "X-Forwarded-Proto": "http"}
    )
    print(response.status_code)
    print(response.text)
except Exception as e:
    import traceback
    traceback.print_exc()
