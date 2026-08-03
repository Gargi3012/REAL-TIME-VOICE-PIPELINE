import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.services.auth_service import hash_password, create_jwt_token

client = TestClient(app)

@pytest.mark.asyncio
async def test_control_plane_endpoints_require_auth():
    # 1. Join endpoint returns 401/403 without authorization header
    response = client.post("/api/livekit/join", json={})
    assert response.status_code in (401, 403)

    # 2. Outbound endpoint returns 401/403 without authorization header
    response = client.post("/api/twilio/outbound", json={"phoneNumber": "+917082968702"})
    assert response.status_code in (401, 403)

@pytest.mark.asyncio
async def test_login_and_access_with_valid_jwt(db_session):
    from app.db.models import User
    from sqlalchemy.future import select

    # Mock user query in database to return our test user
    test_pwd_hash = hash_password("mypassword123")
    
    # We patch the database query to return a mock User model
    mock_user = User(
        username="testadmin",
        hashed_password=test_pwd_hash
    )
    
    # Run login POST request
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute") as mock_exec:
        # Mocking db return value for user lookup
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_user
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_exec.return_value = mock_result
        
        # Test successful login
        login_res = client.post("/api/login", json={"username": "testadmin", "password": "mypassword123"})
        assert login_res.status_code == 200
        token = login_res.json().get("token")
        assert token is not None

        # Test failed login with wrong password
        failed_res = client.post("/api/login", json={"username": "testadmin", "password": "wrongpassword"})
        assert failed_res.status_code == 401

    # Test accessing endpoints with valid token
    headers = {"Authorization": f"Bearer {token}"}
    
    # Livekit Join needs TRANSPORT_MODE to be livekit
    with patch.dict("os.environ", {"TRANSPORT_MODE": "livekit", "LIVEKIT_API_KEY": "key", "LIVEKIT_API_SECRET": "secret"}):
        with patch("app.main.run_voice_session") as mock_run:
            # We patchAccessToken so that it doesn't try to query actual LiveKit server or fail on SDK
            with patch("livekit.api.AccessToken.to_jwt") as mock_jwt:
                mock_jwt.return_value = "mock_livekit_token"
                res = client.post("/api/livekit/join", json={}, headers=headers)
                assert res.status_code == 200
                assert res.json()["token"] == "mock_livekit_token"
