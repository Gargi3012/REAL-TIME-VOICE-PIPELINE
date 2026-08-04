import requests

url = "http://localhost:8000/inbound-call"
data = {
    "To": "+917082968702",
    "From": "+18303546921"
}
# We skip the Twilio signature check for local testing? Wait, handle_inbound_call has Twilio Signature Validation!
