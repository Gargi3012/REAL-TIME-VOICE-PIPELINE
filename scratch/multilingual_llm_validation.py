import asyncio
import os
from loguru import logger
from app.config import GROQ_API_KEY, GROQ_MODEL
from pipecat.frames.frames import UserStartedSpeakingFrame, TextFrame, SystemFrame
from app.llm.prompts import VOICE_SYSTEM_PROMPT

async def run_multilingual_test():
    messages = [
        {"role": "system", "content": VOICE_SYSTEM_PROMPT},
    ]

    async def get_reply(user_text):
        messages.append({"role": "user", "content": user_text})
        logger.info(f"User: {user_text}")
        
        # Groq doesn't directly expose a raw generate method in Pipecat 1.5.0, 
        # so we interact via a temporary Groq API client or just use Pipecat context
        from groq import AsyncGroq
        client = AsyncGroq(api_key=GROQ_API_KEY)
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=100
        )
        reply = response.choices[0].message.content
        logger.info(f"Assistant: {reply}")
        messages.append({"role": "assistant", "content": reply})
        return reply

    print("\n--- English Conversation ---")
    await get_reply("Hi, I want to know about your services.")

    print("\n--- Hindi Conversation ---")
    await get_reply("नमस्ते, मुझे आपके प्लान्स के बारे में जानना है।")

    print("\n--- Hinglish Conversation ---")
    await get_reply("Kya aap pricing bata sakte ho please?")

    print("\n--- Language Switching (Hinglish -> English) ---")
    await get_reply("Thank you, that's exactly what I needed.")

if __name__ == "__main__":
    asyncio.run(run_multilingual_test())
