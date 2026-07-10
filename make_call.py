import os
import argparse
from twilio.rest import Client
from dotenv import load_dotenv

def place_test_call(to_number: str):
    # Load variables from .env
    load_dotenv()
    
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    twilio_number = os.environ.get('TWILIO_PHONE_NUMBER', '')
    
    # We use your ngrok URL combined with the webhook route
    public_url = os.environ.get('PUBLIC_BASE_URL')
    if not public_url:
        print("❌ Error: PUBLIC_BASE_URL is not set in .env! Set it to your ngrok URL.")
        return

    webhook_url = f"{public_url.rstrip('/')}/inbound-call"
    
    # Initialize Twilio Client
    client = Client(account_sid, auth_token)

    print(f"Initiating call from {twilio_number} to {to_number}...")
    print(f"Webhook URL being used: {webhook_url}")

    # Trigger the call
    call = client.calls.create(
        to=to_number,
        from_=twilio_number,
        url=webhook_url
    )
    
    print(f"✅ Call placed successfully! Your phone should be ringing.")
    print(f"Call SID: {call.sid}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make an outbound call using Twilio")
    parser.add_argument("--to", required=True, help="The phone number to call (e.g. +917988207356)")
    args = parser.parse_args()
    
    place_test_call(args.to)
