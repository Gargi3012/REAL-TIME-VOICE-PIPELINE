import os
import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from livekit import api

router = APIRouter()

# Global manager to keep track of frontend connections
frontend_websockets = []

@router.post("/api/livekit/join")
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
            pass
        
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
