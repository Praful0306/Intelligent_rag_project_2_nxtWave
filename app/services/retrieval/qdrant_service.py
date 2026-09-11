import logfire
from qdrant_client import QdrantClient
from app.config import settings
from app.services.retrieval.embeddings import embed_query

qdrant_client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
)


def search_enterprise_knowledge(query: str, limit: int = 15) -> list[dict]:
    """
    Embed query and search Qdrant collection for the top candidates.
    Returns list of dicts with 'content', 'score', and 'source'.
    """
    with logfire.span("Qdrant Search", query=query, limit=limit):
        query_vector = embed_query(query)

        try:
            results = qdrant_client.query_points(
                collection_name=settings.QDRANT_COLLECTION,
                query=query_vector,
                limit=limit,
                with_payload=True,
            ).points
        except Exception:
            results = qdrant_client.search(
                collection_name=settings.QDRANT_COLLECTION,
                query_vector=query_vector,
                limit=limit,
                with_payload=True,
            )

        documents = []
        for point in results:
            payload = point.payload or {}
            content = payload.get("text") or payload.get("content") or ""
            source = payload.get("source", "unknown")
            documents.append({
                "content": content,
                "score": getattr(point, "score", 0.0),
                "source": source,
                "metadata": payload,
            })
        return documents
