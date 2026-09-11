import asyncio
import time
import uuid

from langchain_core.documents import Document
from qdrant_client import models

from app.config import settings
from app.rag import store

# Payload paths, langchain nests document metadata under a "metadata" key.
chat_id_field = "metadata.chat_id"
timestamp_field = "metadata.timestamp"


def ensure_memory() -> None:
    """Create the memory collection and the indexes it needs to filter by user."""

    store.ensure_collection(
        settings.qdrant_memory_collection,
        indexed_fields=[chat_id_field, timestamp_field],
    )


def chat_filter(chat_id: str) -> models.Filter:
    """Restrict a search to a single conversation, this is what separates users."""

    return models.Filter(
        must=[models.FieldCondition(key=chat_id_field, match=models.MatchValue(value=chat_id))]
    )


async def remember(chat_id: str, role: str, content: str) -> None:
    """Store one message of a conversation as a searchable memory."""

    if not content.strip():
        return

    document = Document(
        page_content=content,
        metadata={"chat_id": chat_id, "role": role, "timestamp": time.time()},
    )

    vector_store = store.get_store(settings.qdrant_memory_collection)

    await vector_store.aadd_documents([document], ids=[str(uuid.uuid4())])


async def recall(chat_id: str, query: str, limit: int | None = None) -> list[Document]:
    """Return older messages of this user that are semantically close to the query."""

    vector_store = store.get_store(settings.qdrant_memory_collection)

    return await vector_store.asimilarity_search(
        query=query,
        k=limit or settings.memory_top_k,
        filter=chat_filter(chat_id),
    )


def read_recent(chat_id: str, limit: int) -> list[dict]:
    """Blocking scroll for the newest messages of a chat, ordered by time."""

    points, _ = store.get_client().scroll(
        collection_name=settings.qdrant_memory_collection,
        scroll_filter=chat_filter(chat_id),
        order_by=models.OrderBy(key=timestamp_field, direction=models.Direction.DESC),
        limit=limit,
        with_payload=True,
    )

    return [point.payload or {} for point in points]


async def recent(chat_id: str, limit: int | None = None) -> list[dict]:
    """Return the newest messages of a chat, oldest first, ready to replay."""

    payloads = await asyncio.to_thread(
        read_recent, chat_id, limit or settings.memory_recent_turns
    )

    messages = [
        {
            "role": (payload.get("metadata") or {}).get("role", "user"),
            "content": payload.get("page_content", ""),
        }
        for payload in payloads
    ]

    messages.reverse()

    return messages


async def forget(chat_id: str) -> None:
    """Delete every memory of one conversation."""

    await asyncio.to_thread(
        store.get_client().delete,
        collection_name=settings.qdrant_memory_collection,
        points_selector=chat_filter(chat_id),
    )
