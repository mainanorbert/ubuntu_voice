"""OpenRouter client factory helpers shared across services."""

from openai import AsyncOpenAI, OpenAI


def create_openrouter_async_client(*, api_key: str, base_url: str) -> AsyncOpenAI:
    """Create an AsyncOpenAI client that targets the OpenRouter API."""
    return AsyncOpenAI(base_url=base_url, api_key=api_key)


def create_openrouter_sync_client(*, api_key: str, base_url: str) -> OpenAI:
    """Create a synchronous OpenAI client that targets the OpenRouter API."""
    return OpenAI(base_url=base_url, api_key=api_key)
