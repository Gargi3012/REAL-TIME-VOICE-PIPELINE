from twilio.request_validator import RequestValidator
import os
from dotenv import load_dotenv

load_dotenv()

auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
validator = RequestValidator(auth_token)

url = "https://catalectic-ezra-pisciculturally.ngrok-free.dev/inbound-call"
post_vars = {'To': '+917082968702', 'From': '+18303546921', 'CallSid': 'CA123'}

signature = validator.compute_signature(url, post_vars)
print(f"Computed Signature: {signature}")

is_valid = validator.validate(url, post_vars, signature)
print(f"Is Valid: {is_valid}")
