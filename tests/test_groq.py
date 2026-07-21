import os
from dotenv import load_dotenv
import asyncio
from groq import AsyncGroq

load_dotenv()

async def main():
    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    response = await client.chat.completions.create(
        model=os.getenv("GROQ_MODEL"),
        messages=[{"role": "user", "content": "Hello!"}],
        max_tokens=10
    )
    print(response.choices[0].message.content)

asyncio.run(main())
