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
