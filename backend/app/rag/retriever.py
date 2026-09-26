import os
from typing import Any, Dict, List, Optional

import chromadb


def get_collection():
    """Load the Chroma persistent client and aurelio_kb collection."""
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
    client = chromadb.PersistentClient(path=persist_dir)
    return client.get_or_create_collection("aurelio_kb")


def retrieve(
    query: str,
    k: int = 3,
    category: Optional[str] = None,
    min_confidence: Optional[float] = 1.3,
) -> List[Dict[str, Any]]:
    """
    Retrieve top-k relevant knowledge base chunks for a query.
    
    Args:
        query: The search query string.
        k: Number of top documents to return (default: 3).
        category: Optional category filter string.
        min_confidence: Distance threshold (default: 1.3). If the top result's
            distance exceeds this threshold, returns an empty list signaling
            no relevant knowledge was found.
        
    Returns:
        List of dicts with keys: 'text', 'metadata', 'score'.
    """
    collection = get_collection()

    where_clause = {"category": category} if category else None

    query_params: Dict[str, Any] = {
        "query_texts": [query],
        "n_results": k,
    }
    if where_clause:
        query_params["where"] = where_clause

    results = collection.query(**query_params)

    output: List[Dict[str, Any]] = []
    if results and results.get("documents") and results["documents"]:
        docs = results["documents"][0]
        metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
        distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)

        # If the top result's distance exceeds the threshold, return empty list
        if distances and min_confidence is not None and distances[0] > min_confidence:
            return []

        for doc, meta, dist in zip(docs, metadatas, distances):
            output.append({
                "text": doc,
                "metadata": meta,
                "score": dist,
            })

    return output
