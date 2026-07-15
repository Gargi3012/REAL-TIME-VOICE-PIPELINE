import asyncio
import websockets
import json
import base64
from loguru import logger

async def test_websocket():
    uri = "ws://localhost:8000/ws"
    logger.info(f"Connecting to {uri}")
    async with websockets.connect(uri) as websocket:
        # Send connect event
        connect_msg = {
            "event": "connected",
            "protocol": "Call",
            "version": "1.0.0"
        }
        await websocket.send(json.dumps(connect_msg))
        
        # Send start event
        start_msg = {
            "event": "start",
            "sequenceNumber": "1",
            "start": {
                "streamSid": "MZ1234567890",
                "accountSid": "AC1234567890",
                "callSid": "CA1234567890",
                "tracks": ["inbound"],
                "mediaFormat": {
                    "encoding": "audio/x-mulaw",
                    "sampleRate": 8000,
                    "channels": 1
                }
            }
        }
        await websocket.send(json.dumps(start_msg))
        logger.info("Sent start event, waiting for response...")

        try:
            while True:
                response = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                data = json.loads(response)
                if data["event"] == "media":
                    logger.info("Received MEDIA (audio payload) from Assistant!")
                    break
                elif data["event"] == "mark":
                    logger.info("Received MARK event")
                else:
                    logger.info(f"Received event: {data['event']}")
        except asyncio.TimeoutError:
            logger.error("Timeout: Did not receive any media from Assistant within 5 seconds.")

if __name__ == "__main__":
    asyncio.run(test_websocket())
