from openai import AsyncOpenAI

from app.config import settings

openai_client: AsyncOpenAI | None = None


def get_openai() -> AsyncOpenAI:
    """Return the shared OpenAI client, creating it on first use."""

    global openai_client

    if openai_client is None:

        openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    return openai_client


async def close_openai() -> None:
    """Close the shared OpenAI client, called from the FastAPI lifespan."""

    global openai_client

    if openai_client is not None:

        await openai_client.close()

        openai_client = None
