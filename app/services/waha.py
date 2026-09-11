import httpx

from app.config import settings

# Shared across the process so connections are pooled, not reopened per call.
client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """Return the shared httpx client, creating it on first use."""

    global client

    if client is None:

        headers = {"X-Api-Key": settings.waha_api_key} if settings.waha_api_key else {}

        client = httpx.AsyncClient(
            base_url=settings.waha_url,
            headers=headers,
            timeout=60.0,
        )

    return client


async def close_client() -> None:
    """Close the shared client, called from the FastAPI lifespan on shutdown."""

    global client

    if client is not None:

        await client.aclose()

        client = None


class Waha:
    """Async wrapper over the WAHA HTTP API, bound to one session."""

    def __init__(self, session: str | None = None) -> None:

        self.session = session or settings.waha_session

    async def session_status(self) -> str:
        """Return the session state, WORKING means it can send and receive."""

        response = await get_client().get(f"/api/sessions/{self.session}")
        response.raise_for_status()

        return response.json().get("status", "UNKNOWN")

    async def send_message(self, chat_id: str, text: str) -> dict:
        """Send a text message and return the message WAHA created."""

        payload = {
            "session": self.session,
            "chatId": chat_id,
            "text": text,
        }

        response = await get_client().post("/api/sendText", json=payload)
        response.raise_for_status()

        return response.json()

    async def send_seen(self, chat_id: str, message_id: str | None = None) -> None:
        """Mark the chat as read so the user sees the blue ticks."""

        payload = {"session": self.session, "chatId": chat_id}

        if message_id:
            payload["messageId"] = message_id

        response = await get_client().post("/api/sendSeen", json=payload)
        response.raise_for_status()

    async def get_history_messages(self, chat_id: str, limit: int = 20) -> list[dict]:
        """Fetch the most recent messages of a chat, without downloading media."""

        response = await get_client().get(
            f"/api/{self.session}/chats/{chat_id}/messages",
            params={"limit": limit, "downloadMedia": False},
        )
        response.raise_for_status()

        return response.json()

    async def start_typing(self, chat_id: str) -> None:
        """Show the typing indicator in a chat."""

        payload = {"session": self.session, "chatId": chat_id}

        response = await get_client().post("/api/startTyping", json=payload)
        response.raise_for_status()

    async def stop_typing(self, chat_id: str) -> None:
        """Hide the typing indicator in a chat."""

        payload = {"session": self.session, "chatId": chat_id}

        response = await get_client().post("/api/stopTyping", json=payload)
        response.raise_for_status()

    async def download_media(self, media_url: str) -> bytes:
        """Download an audio or image file that WAHA exposed for a message."""

        response = await get_client().get(media_url)
        response.raise_for_status()

        return response.content
