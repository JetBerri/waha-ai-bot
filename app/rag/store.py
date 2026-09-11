from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient, models

from app.config import settings

# Names langchain_qdrant expects inside the collection, do not rename.
dense_vector_name = ""
sparse_vector_name = "langchain-sparse"

# Known embedding sizes, avoids an API call just to learn the dimension.
embedding_sizes = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

qdrant_client: QdrantClient | None = None
dense_embeddings: OpenAIEmbeddings | None = None
sparse_embeddings: FastEmbedSparse | None = None


def get_client() -> QdrantClient:
    """Return the shared Qdrant client, creating it on first use."""

    global qdrant_client

    if qdrant_client is None:

        qdrant_client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )

    return qdrant_client


def get_dense_embeddings() -> OpenAIEmbeddings:
    """Return the OpenAI embedding model used for semantic search."""

    global dense_embeddings

    if dense_embeddings is None:

        dense_embeddings = OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            api_key=settings.openai_api_key,
        )

    return dense_embeddings


def get_sparse_embeddings() -> FastEmbedSparse:
    """Return the local sparse model used for the keyword half of hybrid search."""

    global sparse_embeddings

    if sparse_embeddings is None:

        sparse_embeddings = FastEmbedSparse(model_name=settings.sparse_embedding_model)

    return sparse_embeddings


def embedding_size() -> int:
    """Return the vector size of the configured embedding model."""

    known = embedding_sizes.get(settings.openai_embedding_model)

    if known:
        return known

    # Unknown model, ask OpenAI once for the real dimension.
    return len(get_dense_embeddings().embed_query("dimension probe"))


def ensure_collection(name: str, indexed_fields: list[str] | None = None) -> None:
    """Create the collection with dense and sparse vectors if it does not exist."""

    client = get_client()

    if not client.collection_exists(name):

        size = embedding_size()

        client.create_collection(
            collection_name=name,
            vectors_config={
                dense_vector_name: models.VectorParams(
                    size=size,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                sparse_vector_name: models.SparseVectorParams(
                    index=models.SparseIndexParams()
                )
            },
        )

    # Payload indexes make chat id filtering and recency ordering fast.
    for field in indexed_fields or []:

        schema = (
            models.PayloadSchemaType.FLOAT
            if field.endswith("timestamp")
            else models.PayloadSchemaType.KEYWORD
        )

        client.create_payload_index(
            collection_name=name,
            field_name=field,
            field_schema=schema,
            wait=True,
        )


def get_store(name: str) -> QdrantVectorStore:
    """Return a hybrid vector store bound to an existing collection."""

    return QdrantVectorStore(
        client=get_client(),
        collection_name=name,
        embedding=get_dense_embeddings(),
        sparse_embedding=get_sparse_embeddings(),
        retrieval_mode=RetrievalMode.HYBRID,
        vector_name=dense_vector_name,
        sparse_vector_name=sparse_vector_name,
    )


def close_client() -> None:
    """Close the shared Qdrant client, called from the FastAPI lifespan."""

    global qdrant_client

    if qdrant_client is not None:

        qdrant_client.close()

        qdrant_client = None
