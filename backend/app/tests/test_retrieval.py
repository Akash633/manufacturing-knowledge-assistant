import pytest
from app.retrieval.bm25 import bm25_engine
from app.retrieval.vector import embedding_provider, FallbackDeterministicVectorizer
from app.retrieval.rrf import reciprocal_rank_fusion

def test_fallback_vectorizer_deterministic():
    vec = FallbackDeterministicVectorizer(dimension=64)
    v1 = vec.embed_text("Spindle warmup cycle 1500 RPM")
    v2 = vec.embed_text("Spindle warmup cycle 1500 RPM")
    assert v1 == v2
    assert len(v1) == 64

def test_bm25_search():
    corpus = [
        {"id": "chunk-1", "content": "DEMO-CNC-01 spindle warm-up procedure requires 10 minutes."},
        {"id": "chunk-2", "content": "Hydraulic clamp pressure must be set to 2.5 MPa."},
        {"id": "chunk-3", "content": "Daily maintenance requires ISO VG 68 way lube oil."},
    ]
    bm25_engine.index_chunks(corpus)
    results = bm25_engine.search("spindle warm-up", top_k=2)
    assert len(results) > 0
    top_chunk_id, score, rank = results[0]
    assert top_chunk_id == "chunk-1"
    assert rank == 1

def test_reciprocal_rank_fusion():
    bm25_ranks = [("doc-A", 12.5, 1), ("doc-B", 8.2, 2)]
    vector_ranks = [("doc-B", 0.88, 1), ("doc-A", 0.75, 2)]

    fused = reciprocal_rank_fusion(bm25_ranks, vector_ranks, k=60, top_n=2)
    assert len(fused) == 2
    # doc-A score: 1/(60+1) + 1/(60+2) = 1/61 + 1/62 = 0.01639 + 0.01612 = 0.03251
    # doc-B score: 1/(60+2) + 1/(60+1) = identical
    assert fused[0]["chunk_id"] in ["doc-A", "doc-B"]
