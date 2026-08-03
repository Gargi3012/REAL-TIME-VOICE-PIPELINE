import sys

with open("app/main.py", "r") as f:
    content = f.read()

# 1. Add APP_STATE and ACTIVE_STREAMS
content = content.replace(
    "from contextlib import asynccontextmanager\n\n@asynccontextmanager",
    "from contextlib import asynccontextmanager\n\nAPP_STATE = {\"is_ready\": False}\nACTIVE_STREAMS = set()\n\n@asynccontextmanager"
)

# 2. Update lifespan for readiness and retry
lifespan_old = """    try:
        db_manager.init_db()
        async with db_manager.get_session() as db:
            from sqlalchemy import text
            await db.execute(text("SELECT 1"))
        logger.info("Database connection pool initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database on startup: {e}")
        # We do not crash the app so that we don't break the pipeline if DB is temporarily down.
        # It will retry on the first call.
    
    yield
    
    logger.info("Shutting down database connection pool...")
    await db_manager.close()

app = FastAPI(lifespan=lifespan)"""

lifespan_new = """    try:
        db_manager.init_db()
        # Retry mechanism for transient DB startup failures
        import asyncio
        for attempt in range(3):
            try:
                async with db_manager.get_session() as db:
                    from sqlalchemy import text
                    await db.execute(text("SELECT 1"))
                break
            except Exception as retry_err:
                if attempt == 2:
                    raise retry_err
                await asyncio.sleep(1.0)
        logger.info("Database connection pool initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database on startup (will degrade gracefully): {e}")
        # We do not crash the app so that we don't break the pipeline if DB is temporarily down.

    # Mark as ready regardless of DB to allow graceful degradation
    APP_STATE["is_ready"] = True
    
    yield
    
    logger.info("Shutting down database connection pool...")
    APP_STATE["is_ready"] = False
    await db_manager.close()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health_check():
    \"\"\"Backend readiness verification before accepting requests.\"\"\"
    if APP_STATE.get("is_ready"):
        return {"status": "ok"}
    raise HTTPException(status_code=503, detail="Service not ready")"""

content = content.replace(lifespan_old, lifespan_new)

# 3. Webhook readiness check
webhook_old = """    webhook_processing_start = time.perf_counter()
    logger.info("Incoming Twilio call received")
    
    form_data = await request.form()"""

webhook_new = """    webhook_processing_start = time.perf_counter()
    logger.info("Incoming Twilio call received")
    
    # ── Backend Readiness ──
    if not APP_STATE.get("is_ready"):
        logger.warning("Incoming Twilio call rejected: Backend not ready.")
        raise HTTPException(status_code=503, detail="Service not ready")
        
    form_data = await request.form()"""

content = content.replace(webhook_old, webhook_new)

# 4. DB Pre-fetch retry in webhook
db_fetch_old = """    try:
        async def fetch_db():
            async with db_manager.get_session() as db:
                client = await ClientRepository.get_or_create_client(db, phone_number)
                summary_text = await SessionRepository.get_summary(db, client.id)
                return str(client.id), summary_text
                
        # Wait up to 3 seconds for the DB, so we don't block Twilio's 15s webhook timeout"""

db_fetch_new = """    try:
        async def fetch_db():
            # Robust retry mechanism for transient failures
            import asyncio
            for attempt in range(2):
                try:
                    async with db_manager.get_session() as db:
                        client = await ClientRepository.get_or_create_client(db, phone_number)
                        summary_text = await SessionRepository.get_summary(db, client.id)
                        return str(client.id), summary_text
                except Exception as db_err:
                    if attempt == 1:
                        raise db_err
                    await asyncio.sleep(0.5)
                
        # Wait up to 3 seconds for the DB, so we don't block Twilio's 15s webhook timeout"""

content = content.replace(db_fetch_old, db_fetch_new)

# 5. WebSocket accept and deduplication
ws_old = """@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    \"\"\"Twilio WebSocket endpoint for Pipecat audio stream.\"\"\"
    media_stream_connection = time.perf_counter()
    await websocket.accept()
    logger.info("WebSocket connection accepted from Twilio")
    
    # Twilio sends a 'connected' event, then a 'start' event
    import json
    stream_sid = None
    
    # Wait for the start event
    for _ in range(5): # Don't loop forever
        data = await websocket.receive_text()
        msg = json.loads(data)
        if msg.get("event") == "start":
            stream_sid = msg["start"]["streamSid"]
            
            # Extract custom parameters from the start event"""

ws_new = """@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    \"\"\"Twilio WebSocket endpoint for Pipecat audio stream.\"\"\"
    media_stream_connection = time.perf_counter()
    try:
        await websocket.accept()
        logger.info("WebSocket connection accepted from Twilio")
    except Exception as accept_err:
        logger.error(f"Failed to accept WebSocket connection: {accept_err}")
        return
    
    # Twilio sends a 'connected' event, then a 'start' event
    import json
    stream_sid = None
    
    try:
        # Wait for the start event
        for _ in range(5): # Don't loop forever
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("event") == "start":
                stream_sid = msg["start"]["streamSid"]
                
                # Prevention of duplicate session creation
                if stream_sid in ACTIVE_STREAMS:
                    logger.warning(f"Duplicate WebSocket connection for stream {stream_sid}. Rejecting.")
                    return
                ACTIVE_STREAMS.add(stream_sid)
                
                # Extract custom parameters from the start event"""

content = content.replace(ws_old, ws_new)

# 6. WebSocket cleanup
ws_cleanup_old = """    finally:
        try:
            from fastapi.websockets import WebSocketState
            if websocket.client_state != WebSocketState.DISCONNECTED:
                logger.info("Closing Twilio WebSocket connection gracefully")
                await websocket.close()
        except Exception as close_err:
            logger.warning(f"Error while closing Twilio WebSocket: {close_err}")


# ── Core Pipeline Session ───────────────────────────────────────────────"""

ws_cleanup_new = """    finally:
        try:
            from fastapi.websockets import WebSocketState
            if websocket.client_state != WebSocketState.DISCONNECTED:
                logger.info("Closing Twilio WebSocket connection gracefully")
                await websocket.close()
        except Exception as close_err:
            logger.warning(f"Error while closing Twilio WebSocket: {close_err}")
            
        # Cleanup of abandoned streams
        if stream_sid and stream_sid in ACTIVE_STREAMS:
            ACTIVE_STREAMS.remove(stream_sid)


# ── Core Pipeline Session ───────────────────────────────────────────────"""

content = content.replace(ws_cleanup_old, ws_cleanup_new)

with open("app/main.py", "w") as f:
    f.write(content)

print("Patch applied.")
