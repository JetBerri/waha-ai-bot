import argparse
import asyncio
import uuid
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.rag import hybrid, store

# Extensions the ingester knows how to read.
text_suffixes = {".txt", ".md"}
pdf_suffixes = {".pdf"}


def read_pdf(path: Path) -> str:
    """Extract plain text from a pdf, page by page."""

    from pypdf import PdfReader

    reader = PdfReader(str(path))

    return "\n".join(page.extract_text() or "" for page in reader.pages)


def read_file(path: Path) -> str:
    """Return the text content of a supported file."""

    if path.suffix.lower() in pdf_suffixes:
        return read_pdf(path)

    return path.read_text(encoding="utf-8", errors="ignore")


def collect_files(root: Path) -> list[Path]:
    """List every supported file under a directory, or the file itself."""

    supported = text_suffixes | pdf_suffixes

    if root.is_file():
        return [root] if root.suffix.lower() in supported else []

    return sorted(p for p in root.rglob("*") if p.suffix.lower() in supported)


async def ingest(root: Path, chunk_size: int = 1000, chunk_overlap: int = 200) -> int:
    """Split every supported file under root and load it into the knowledge base."""

    hybrid.ensure_knowledge()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    documents: list[Document] = []

    for path in collect_files(root):

        text = read_file(path).strip()

        if not text:
            continue

        for chunk in splitter.split_text(text):
            documents.append(Document(page_content=chunk, metadata={"source": path.name}))

    if not documents:
        return 0

    vector_store = store.get_store(settings.qdrant_knowledge_collection)

    await vector_store.aadd_documents(documents, ids=[str(uuid.uuid4()) for _ in documents])

    return len(documents)


def main() -> None:
    """Command line entry point: python -m app.rag.ingest app/rag/data"""

    parser = argparse.ArgumentParser(description="Load documents into the knowledge base")
    parser.add_argument("path", type=Path, help="File or directory to ingest")
    arguments = parser.parse_args()

    total = asyncio.run(ingest(arguments.path))

    print(f"Ingested {total} chunks into '{settings.qdrant_knowledge_collection}'")


if __name__ == "__main__":
    main()
