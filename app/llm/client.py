"""Groq client integration for streaming LLM text responses."""

import os
from typing import AsyncGenerator, List, Optional
from loguru import logger
from groq import AsyncGroq

from app.session.message import Message


class GroqLLMClient:
    """Client for Groq LLM API, designed for real-time streaming completions."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """Initialise the Groq LLM client.

        Args:
            api_key: Optional Groq API key. If not provided, it is read
                     from the GROQ_API_KEY environment variable.
            model: Optional Model identifier. If not provided, it is read
                   from GROQ_MODEL, defaulting to "llama-3.1-8b-instant".
        """
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model or os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
        if not self.api_key:
            logger.error("Failed to initialise GroqLLMClient: GROQ_API_KEY is not set.")
            raise ValueError(
                "GROQ_API_KEY is not set. Please set the GROQ_API_KEY environment variable."
            )

        self.client = AsyncGroq(api_key=self.api_key)
        logger.info(
            "GroqLLMClient initialised successfully | model={model}",
            model=self.model,
        )

    async def stream_response(
        self,
        messages: List[Message],
    ) -> AsyncGenerator[str, None]:
        """Convert list of Message objects to chat-completion dicts and stream chunks.

        Args:
            messages: List of Message objects containing history.

        Yields:
            str: Generated text chunk.
        """
        if not messages:
            logger.warning("stream_response called with empty message history.")
            return

        # Convert message list to the dictionary format expected by Groq chat completion API.
        # We only keep 'role' and 'content' fields to match standard completion parameters.
        formatted_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        logger.debug(
            "Sending chat completion request to Groq | model={model} | messages={count}",
            model=self.model,
            count=len(formatted_messages),
        )

        try:
            # Request a streaming response from Groq
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,  # type: ignore
                stream=True,
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error("Error occurred while streaming from Groq API: {error}", error=e)
            raise
