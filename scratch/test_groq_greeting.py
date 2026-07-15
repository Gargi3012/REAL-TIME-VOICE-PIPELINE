import asyncio
from loguru import logger
from app.config import GROQ_API_KEY, GROQ_MODEL
from app.llm.prompts import VOICE_SYSTEM_PROMPT
from groq import AsyncGroq

async def test_greeting():
    client = AsyncGroq(api_key=GROQ_API_KEY)
    messages = [{"role": "system", "content": VOICE_SYSTEM_PROMPT}]
    
    logger.info("Requesting initial greeting from Groq...")
    response = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        max_tokens=100
    )
    reply = response.choices[0].message.content
    logger.info(f"Generated Greeting: {reply}")

if __name__ == "__main__":
    asyncio.run(test_greeting())
