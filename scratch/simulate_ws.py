import asyncio
import json
import websockets

async def main():
    async with websockets.connect("ws://localhost:8000/ws") as websocket:
        start_msg = {
            "event": "start",
            "start": {
                "streamSid": "test_stream_123",
                "customParameters": {
                    "phone": "+917082968702",
                    "client_id": "bb0c6de1-2a90-4d56-a09c-68e7ec8d39e3",
                    "webhook_processing_start": "0.0"
                }
            }
        }
        await websocket.send(json.dumps(start_msg))
        # Wait a few seconds to let it process
        await asyncio.sleep(2)
        await websocket.close()

if __name__ == "__main__":
    asyncio.run(main())
