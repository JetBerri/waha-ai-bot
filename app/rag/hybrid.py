from langchain_core.documents import Document

from app.config import settings
from app.rag import store

# Payload path used to group knowledge by origin file.
source_field = "metadata.source"


def ensure_knowledge() -> None:
    """Create the knowledge collection used by hybrid retrieval."""

    store.ensure_collection(
        settings.qdrant_knowledge_collection,
        indexed_fields=[source_field],
    )


async def search(query: str, limit: int | None = None) -> list[Document]:
    """Hybrid search over the knowledge base, dense semantics plus sparse keywords."""

    vector_store = store.get_store(settings.qdrant_knowledge_collection)

    return await vector_store.asimilarity_search(
        query=query,
        k=limit or settings.knowledge_top_k,
    )


def format_context(documents: list[Document]) -> str:
    """Render retrieved documents as a plain block the model can read."""

    if not documents:
        return "No hay documentación relevante para esta pregunta."

    blocks = []

    for document in documents:

        source = document.metadata.get("source", "desconocido")
        blocks.append(f"[fuente: {source}]\n{document.page_content}")

    return "\n\n".join(blocks)


async def build_context(query: str) -> str:
    """Retrieve and format the knowledge context for one question."""

    return format_context(await search(query))
