import requests
from dotenv import load_dotenv
import os

load_dotenv()
url = "https://catalectic-ezra-pisciculturally.ngrok-free.dev/inbound-call"
res = requests.post(url, data={"To": "+123"})
print(res.status_code)
