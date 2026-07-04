

import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

DAILY_API_KEY = os.getenv("DAILY_API_KEY")
DAILY_API_URL = "https://api.daily.co/v1"


async def create_daily_room(room_name: str = None) -> dict:
    headers = {
        "Authorization": f"Bearer {DAILY_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "properties": {
            "enable_screenshare": False,
            "enable_chat": False,
            "start_video_off": True,   # we only need audio
            "start_audio_off": False,
            "exp": None,  # room doesn't auto-expire; set a unix timestamp if you want
        }
    }

    if room_name:
        payload["name"] = room_name

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{DAILY_API_URL}/rooms", headers=headers, json=payload
        ) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise Exception(f"Failed to create Daily room: {data}")
            return data


async def create_meeting_token(room_name: str) -> str:
    """
    Creates a short-lived access token for a specific room.
    Needed so the voice agent (bot) can join the room securely.
    """
    headers = {
        "Authorization": f"Bearer {DAILY_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "properties": {
            "room_name": room_name,
            "is_owner": True,
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{DAILY_API_URL}/meeting-tokens", headers=headers, json=payload
        ) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise Exception(f"Failed to create meeting token: {data}")
            return data["token"]


# Quick manual test -> run: python src/daily_room.py
if __name__ == "__main__":
    import asyncio

    async def main():
        room = await create_daily_room("test-room-gargi")
        print("Room created:", room["url"])

        token = await create_meeting_token(room["name"])
        print("Token:", token)

    asyncio.run(main())