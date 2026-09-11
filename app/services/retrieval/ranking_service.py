import logfire

_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder

            _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception as e:
            logfire.warning(
                f"Could not load CrossEncoder: {e}. Falling back to passthrough."
            )
            _reranker = "passthrough"
    return _reranker


def rerank_documents(query: str, documents: list[str], top_n: int = 5) -> list[str]:
    """
    Reranks documents based on query relevance using a CrossEncoder.
    Falls back to original order if reranker is unavailable.
    """
    if not documents:
        return []

    reranker = _get_reranker()
    if reranker == "passthrough" or reranker is None:
        return documents[:top_n]

    with logfire.span("CrossEncoder Rerank", doc_count=len(documents), top_n=top_n):
        try:
            pairs = [[query, doc] for doc in documents]
            scores = reranker.predict(pairs)
            scored_docs = sorted(
                zip(documents, scores), key=lambda x: x[1], reverse=True
            )
            return [doc for doc, _ in scored_docs[:top_n]]
        except Exception as e:
            logfire.warning(
                f"Reranking failed: {e}. Using un-reranked documents."
            )
            return documents[:top_n]
