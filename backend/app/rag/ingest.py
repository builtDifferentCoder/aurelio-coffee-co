import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List

import chromadb
import frontmatter
from langchain_text_splitters import MarkdownHeaderTextSplitter


def get_kb_directory() -> Path:
    """Resolve the knowledge base directory path."""
    kb_path = Path(os.getenv("KB_DIR", "./data/knowledge_base"))
    if kb_path.exists() and kb_path.is_dir():
        return kb_path
    
    # Fallback relative to this file: backend/data/knowledge_base
    fallback_path = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge_base"
    if fallback_path.exists() and fallback_path.is_dir():
        return fallback_path

    raise FileNotFoundError(f"Knowledge base directory not found at {kb_path} or {fallback_path}")


def ingest_knowledge_base():
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
    print(f"Connecting to Chroma at: {persist_dir}")
    client = chromadb.PersistentClient(path=persist_dir)

    collection = client.get_or_create_collection("aurelio_kb")

    kb_dir = get_kb_directory()
    print(f"Reading markdown files from: {kb_dir}")

    # Collect all markdown files
    md_files = sorted(list(kb_dir.glob("*.md")))
    if not md_files:
        # Check subdirectories if any
        md_files = sorted(list(kb_dir.rglob("*.md")))

    headers_to_split_on = [("##", "Header 2")]
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=False,
    )

    all_ids: List[str] = []
    all_documents: List[str] = []
    all_metadatas: List[Dict[str, Any]] = []

    files_processed = 0

    for file_path in md_files:
        files_processed += 1
        filename = file_path.name

        with open(file_path, "r", encoding="utf-8") as f:
            post = frontmatter.load(f)

        category = str(post.metadata.get("category", "")).strip()
        title = str(post.metadata.get("title", "")).strip()
        body = post.content.strip()

        # Split on ## headers, fallback to whole doc if no ## headers found
        split_docs = splitter.split_text(body)
        chunks = [doc.page_content.strip() for doc in split_docs if doc.page_content.strip()]
        if not chunks and body:
            chunks = [body]

        for chunk_idx, chunk_text in enumerate(chunks):
            # Stable deterministic ID: hash of filename + chunk_index
            hash_input = f"{filename}_{chunk_idx}".encode("utf-8")
            chunk_id = hashlib.sha256(hash_input).hexdigest()

            metadata = {
                "source": filename,
                "category": category,
                "title": title,
            }

            all_ids.append(chunk_id)
            all_documents.append(chunk_text)
            all_metadatas.append(metadata)

    # Upsert all chunks to ensure idempotency
    if all_ids:
        collection.upsert(
            ids=all_ids,
            documents=all_documents,
            metadatas=all_metadatas,
        )

    # Print summary
    print("\n--- Ingestion Summary ---")
    print(f"Total files processed: {files_processed}")
    print(f"Total chunks created: {len(all_ids)}")
    print(f"Total items in collection: {collection.count()}")

    if all_documents:
        print("\n--- Sample Chunk ---")
        print(f"ID: {all_ids[0]}")
        print(f"Metadata: {all_metadatas[0]}")
        print("Document Content:")
        print("-" * 40)
        print(all_documents[0])
        print("-" * 40)


if __name__ == "__main__":
    ingest_knowledge_base()
