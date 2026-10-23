from typing import List, Dict, Any, Tuple
from app.core.config import settings

def reciprocal_rank_fusion(
    bm25_results: List[Tuple[str, float, int]], # (chunk_id, bm25_score, rank)
    vector_results: List[Tuple[str, float, int]], # (chunk_id, vector_score, rank)
    k: int = 60,
    top_n: int = 5
) -> List[Dict[str, Any]]:
    """
    Combines ranked lists from BM25 and Vector retrieval using Reciprocal Rank Fusion.
    RRF Score: sum( 1.0 / (k + rank) )
    Tracks individual component ranks and scores for full transparency and explainability.
    """
    scores: Dict[str, float] = {}
    details: Dict[str, Dict[str, Any]] = {}

    # Process BM25 rankings
    for chunk_id, bm25_score, rank in bm25_results:
        rrf_contrib = 1.0 / (k + rank)
        scores[chunk_id] = scores.get(chunk_id, 0.0) + rrf_contrib
        if chunk_id not in details:
            details[chunk_id] = {
                "chunk_id": chunk_id,
                "bm25_rank": rank,
                "bm25_score": bm25_score,
                "vector_rank": None,
                "vector_score": None,
            }
        else:
            details[chunk_id]["bm25_rank"] = rank
            details[chunk_id]["bm25_score"] = bm25_score

    # Process Vector rankings
    for chunk_id, vector_score, rank in vector_results:
        rrf_contrib = 1.0 / (k + rank)
        scores[chunk_id] = scores.get(chunk_id, 0.0) + rrf_contrib
        if chunk_id not in details:
            details[chunk_id] = {
                "chunk_id": chunk_id,
                "bm25_rank": None,
                "bm25_score": None,
                "vector_rank": rank,
                "vector_score": vector_score,
            }
        else:
            details[chunk_id]["vector_rank"] = rank
            details[chunk_id]["vector_score"] = vector_score

    # Sort candidates by combined RRF score descending
    sorted_chunks = sorted(scores.items(), key=lambda item: item[1], reverse=True)

    fused_results = []
    for rank, (chunk_id, rrf_score) in enumerate(sorted_chunks[:top_n], start=1):
        item = details[chunk_id]
        item["rrf_score"] = rrf_score
        item["fused_rank"] = rank
        fused_results.append(item)

    return fused_results
