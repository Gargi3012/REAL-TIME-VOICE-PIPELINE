import os
import asyncio
import time
from datetime import datetime
from collections import defaultdict
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from livekit import api
from loguru import logger

router = APIRouter()

# Global manager to keep track of frontend connections
frontend_websockets = []

# --- Security Dependencies ---
security = HTTPBearer()
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key")

rate_limit_records = defaultdict(list)
RATE_LIMIT_REQUESTS = 5
RATE_LIMIT_WINDOW = 60

async def rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    
    # Cleanup old records
    rate_limit_records[client_ip] = [
        t for t in rate_limit_records[client_ip] 
        if current_time - t < RATE_LIMIT_WINDOW
    ]
    
    if len(rate_limit_records[client_ip]) >= RATE_LIMIT_REQUESTS:
        logger.warning(f"SECURITY: Rate limit exceeded for IP {client_ip} on /api/livekit/join")
        raise HTTPException(status_code=429, detail="Too many requests")
        
    rate_limit_records[client_ip].append(current_time)

async def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        logger.info(f"SECURITY: Successful authentication for user {payload.get('sub', 'unknown')} on /api/livekit/join")
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("SECURITY: Expired JWT token attempt")
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        logger.warning("SECURITY: Invalid JWT token attempt")
        raise HTTPException(status_code=403, detail="Invalid authentication token")

from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/api/login")
async def login(payload: LoginRequest):
    from app.db.connection import db_manager
    from app.db.models import User
    from app.services.auth_service import verify_password, create_jwt_token
    from sqlalchemy.future import select
    
    try:
        async with db_manager.get_session() as db:
            result = await db.execute(select(User).where(User.username == payload.username))
            user = result.scalars().first()
    except Exception as db_err:
        logger.error(f"Database error during login: {db_err}")
        raise HTTPException(status_code=500, detail="Database access error")
        
    if not user or not verify_password(user.hashed_password, payload.password):
        logger.warning(f"SECURITY: Failed login attempt for user '{payload.username}'")
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    token = create_jwt_token(payload.username)
    logger.info(f"SECURITY: Successful login for user '{payload.username}'")
    return {"token": token}

@router.post("/api/register")
async def register(payload: LoginRequest):
    from app.db.connection import db_manager
    from app.db.models import User
    from app.services.auth_service import hash_password
    from sqlalchemy.future import select

    if not payload.username or len(payload.username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters long")
    if not payload.password or len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
        
    try:
        async with db_manager.get_session() as db:
            result = await db.execute(select(User).where(User.username == payload.username))
            existing_user = result.scalars().first()
            
            if existing_user:
                raise HTTPException(status_code=400, detail="Username already exists")
                
            hashed_pwd = hash_password(payload.password)
            new_user = User(
                username=payload.username,
                hashed_password=hashed_pwd
            )
            db.add(new_user)
            await db.commit()
            
            logger.info(f"SECURITY: Successfully registered new user '{payload.username}' in Neon database.")
            return {"status": "success", "message": "User registered successfully"}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Database error during registration: {e}")
        raise HTTPException(status_code=500, detail="Failed to register user")

@router.post("/api/livekit/join", dependencies=[Depends(rate_limit), Depends(verify_jwt)])
async def join_livekit_room(request: dict = None):
    if os.getenv("TRANSPORT_MODE") != "livekit":
        raise HTTPException(status_code=400, detail="Not in LiveKit mode")
        
    # Generate token
    from app.config import LIVEKIT_ROOM
    room_name = LIVEKIT_ROOM
    participant_name = "user-frontend"
    
    try:
        token = api.AccessToken(
            os.getenv("LIVEKIT_API_KEY"), 
            os.getenv("LIVEKIT_API_SECRET")
        )
        token = token.with_identity(participant_name)
        token = token.with_name(participant_name)
        token = token.with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
        ))
        
        try:
            from app.main import run_voice_session
            asyncio.create_task(run_voice_session())
        except Exception as e:
            logger.exception(f"Failed to start voice session background task: {e}")
        
        return {
            "token": token.to_jwt(),
            "roomUrl": os.getenv("LIVEKIT_URL")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate token: {str(e)}")


@router.post("/api/twilio/outbound", dependencies=[Depends(verify_jwt)])
async def trigger_outbound_call(payload: dict):
    phone_number = payload.get("phoneNumber")
    if not phone_number:
        raise HTTPException(status_code=400, detail="phoneNumber is required")
        
    try:
        from Pillar_2.outbound_call import place_outbound_call
        call_sid = await asyncio.to_thread(place_outbound_call, phone_number)
        return {"status": "success", "callSid": call_sid}
    except Exception as e:
        logger.exception(f"Failed to place outbound call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/frontend")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    frontend_websockets.append(websocket)
    
    # Send initial transport mode
    await websocket.send_json({
        "event": "transport_mode",
        "mode": os.getenv("TRANSPORT_MODE", "livekit"),
        "timestamp": datetime.now().isoformat()
    })
    
    try:
        while True:
            # Keep connection open, frontend only receives
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in frontend_websockets:
            frontend_websockets.remove(websocket)


async def broadcast_frontend_event(event_name: str, data: dict = None):
    """
    Helper function to call from Pipeline to push state to the UI.
    """
    if data is None:
        data = {}
    payload = {
        "event": event_name, 
        "timestamp": datetime.now().isoformat(),
        **data
    }
    
    # Send to all connected frontends
    disconnected = []
    for ws in frontend_websockets:
        try:
            await ws.send_json(payload)
        except Exception:
            disconnected.append(ws)
            
    # Cleanup stale connections
    for ws in disconnected:
        if ws in frontend_websockets:
            frontend_websockets.remove(ws)
