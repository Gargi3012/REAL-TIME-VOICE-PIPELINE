import asyncio
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
try:
    response = client.post("/inbound-call", data={"To": "+917082968702"})
    print(response.status_code)
    print(response.text)
except Exception as e:
    import traceback
    traceback.print_exc()
