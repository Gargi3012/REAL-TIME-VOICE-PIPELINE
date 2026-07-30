import argparse
import urllib.parse
import os
from dotenv import load_dotenv

from loguru import logger
from twilio.rest import Client

# Load environment variables
load_dotenv(override=True)


def place_outbound_call(to_number: str, company_context: str | None = None) -> str:
    public_base_url = os.getenv("PUBLIC_BASE_URL", "")
    twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER", "")

    if not public_base_url:
        raise ValueError(
            "PUBLIC_BASE_URL is empty in .env — set it to your current ngrok URL first "
            "(e.g. https://xxxx.ngrok-free.app), then re-run this script."
        )

    client = Client(twilio_account_sid, twilio_auth_token)

    # Reuse the exact same webhook used for inbound calls — it just returns
    # TwiML that opens the media stream, regardless of who initiated the call.
    webhook_url = f"{public_base_url.rstrip('/')}/inbound-call"

    # Optional: pass company context through as a query param so the webhook
    # can thread it into build_pipeline_task(..., company_context=...).
    if company_context:
        webhook_url += f"?company_context={urllib.parse.quote(company_context)}"

    logger.info(f"Placing outbound call: to={to_number}, from={twilio_phone_number}, url={webhook_url}")

    call = client.calls.create(
        to=to_number,
        from_=twilio_phone_number,
        url=webhook_url,
    )

    logger.info(f"Outbound call placed. Twilio Call SID: {call.sid}")
    return call.sid


def main():
    parser = argparse.ArgumentParser(description="Place an outbound call through the voice agent")
    parser.add_argument("--to", required=True, help="Phone number to call, in E.164 format, e.g. +91XXXXXXXXXX")
    parser.add_argument("--company-context", default=None, help="Optional B2B record text to inject into the call")
    args = parser.parse_args()

    place_outbound_call(args.to, args.company_context)


if __name__ == "__main__":
    main()