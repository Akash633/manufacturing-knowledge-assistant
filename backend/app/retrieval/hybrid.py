import time
import json
from typing import List, Dict, Any, Optional
import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.governance.revision_rules import revision_governance
from app.schemas.retrieval import RetrievalQuery, RetrievedPassage, RetrievalResponse, RetrievalModeEnum
from app.retrieval.bm25 import bm25_engine
from app.retrieval.vector import embedding_provider
from app.retrieval.rrf import reciprocal_rank_fusion

class HybridRetriever:
    """
    Coordinates BM25 keyword search, semantic dense vector search,
    and Reciprocal Rank Fusion (RRF) with revision governance filtering.
    """
    def search(
        self,
        db: Session,
        query_param: RetrievalQuery,
    ) -> RetrievalResponse:
        start_time = time.perf_counter()

        # Step 1: Query eligible documents from DB based on revision governance
        doc_query = db.query(Document)
        if query_param.machine_model:
            doc_query = doc_query.filter(
                (Document.machine_model == query_param.machine_model) | (Document.machine_model == "ALL")
            )
        if query_param.target_document_id:
            doc_query = doc_query.filter(Document.id == query_param.target_document_id)

        candidates = doc_query.all()
        authority_by_doc = {
            doc.id: revision_governance.evaluate_authority(doc).is_authoritative
            for doc in candidates
        }
        valid_docs = [
            doc for doc in candidates
            if not query_param.filter_approved_only or authority_by_doc[doc.id]
        ]
        doc_map = {d.id: d for d in valid_docs}
        valid_doc_ids = list(doc_map.keys())

        if not valid_doc_ids:
            latency = (time.perf_counter() - start_time) * 1000
            return RetrievalResponse(
                query=query_param.query,
                retrieval_mode=query_param.mode.value,
                total_chunks_searched=0,
                retrieval_latency_ms=latency,
                results=[],
                provider_used=embedding_provider.provider_name,
                fallback_triggered=False,
            )

        # Step 2: Fetch all chunks belonging to valid documents
        chunks = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id.in_(valid_doc_ids))
            .all()
        )
        total_chunks = len(chunks)
        if total_chunks == 0:
            latency = (time.perf_counter() - start_time) * 1000
            return RetrievalResponse(
                query=query_param.query,
                retrieval_mode=query_param.mode.value,
                total_chunks_searched=0,
                retrieval_latency_ms=latency,
                results=[],
                provider_used=embedding_provider.provider_name,
                fallback_triggered=False,
            )

        chunk_dict = {c.id: c for c in chunks}

        # Step 3: Execute BM25 Keyword Search
        bm25_results = []
        if query_param.mode in [RetrievalModeEnum.BM25, RetrievalModeEnum.HYBRID]:
            chunk_data_for_bm25 = [{"id": c.id, "content": c.content} for c in chunks]
            bm25_engine.index_chunks(chunk_data_for_bm25)
            # Retrieve up to 20 candidates for fusion
            bm25_results = bm25_engine.search(query_param.query, top_k=max(20, query_param.top_k * 3))

        # Step 4: Execute Vector Retrieval
        vector_results = []
        if query_param.mode in [RetrievalModeEnum.VECTOR, RetrievalModeEnum.HYBRID]:
            query_emb = np.array(embedding_provider.embed_text(query_param.query), dtype=np.float32)
            q_norm = np.linalg.norm(query_emb)
            if q_norm > 1e-6:
                query_emb = query_emb / q_norm

            scored_chunks = []
            for c in chunks:
                if c.embedding_vector_json:
                    c_emb = np.array(json.loads(c.embedding_vector_json), dtype=np.float32)
                else:
                    # On-the-fly embedding if chunk was saved without one
                    c_emb = np.array(embedding_provider.embed_text(c.content), dtype=np.float32)
                    c.embedding_vector_json = json.dumps(c_emb.tolist())
                    db.commit()

                c_norm = np.linalg.norm(c_emb)
                if c_norm > 1e-6:
                    c_emb = c_emb / c_norm
                sim = float(np.dot(query_emb, c_emb))
                scored_chunks.append((c.id, sim))

            # Sort descending
            scored_chunks.sort(key=lambda x: x[1], reverse=True)
            for rank, (cid, sim) in enumerate(scored_chunks[:max(20, query_param.top_k * 3)], start=1):
                if sim > 0.05:
                    vector_results.append((cid, sim, rank))

        # Step 5: Rank Aggregation
        final_passages: List[RetrievedPassage] = []

        if query_param.mode == RetrievalModeEnum.HYBRID:
            fused = reciprocal_rank_fusion(
                bm25_results=bm25_results,
                vector_results=vector_results,
                k=settings.RRF_K,
                top_n=query_param.top_k,
            )
            for item in fused:
                cid = item["chunk_id"]
                c = chunk_dict.get(cid)
                if not c:
                    continue
                d = doc_map.get(c.document_id)
                images = json.loads(c.image_paths_json) if c.image_paths_json else []
                
                final_passages.append(
                    RetrievedPassage(
                        chunk_id=c.id,
                        document_id=d.id,
                        document_number=d.document_number,
                        document_title=d.title,
                        revision=d.revision,
                        approval_status=d.approval_status,
                        is_authoritative=authority_by_doc[d.id],
                        page_number=c.page_number,
                        section_title=c.section_title,
                        content=c.content,
                        score=round(item["rrf_score"], 5),
                        bm25_rank=item.get("bm25_rank"),
                        vector_rank=item.get("vector_rank"),
                        bm25_score=round(item["bm25_score"], 4) if item.get("bm25_score") is not None else None,
                        vector_score=round(item["vector_score"], 4) if item.get("vector_score") is not None else None,
                        has_images=c.has_images,
                        image_paths=images,
                        ocr_applied=c.ocr_applied,
                    )
                )
        elif query_param.mode == RetrievalModeEnum.BM25:
            for cid, score, rank in bm25_results[:query_param.top_k]:
                c = chunk_dict.get(cid)
                if not c:
                    continue
                d = doc_map.get(c.document_id)
                images = json.loads(c.image_paths_json) if c.image_paths_json else []
                final_passages.append(
                    RetrievedPassage(
                        chunk_id=c.id,
                        document_id=d.id,
                        document_number=d.document_number,
                        document_title=d.title,
                        revision=d.revision,
                        approval_status=d.approval_status,
                        is_authoritative=authority_by_doc[d.id],
                        page_number=c.page_number,
                        section_title=c.section_title,
                        content=c.content,
                        score=round(score, 4),
                        bm25_rank=rank,
                        bm25_score=round(score, 4),
                        has_images=c.has_images,
                        image_paths=images,
                        ocr_applied=c.ocr_applied,
                    )
                )
        elif query_param.mode == RetrievalModeEnum.VECTOR:
            for cid, score, rank in vector_results[:query_param.top_k]:
                c = chunk_dict.get(cid)
                if not c:
                    continue
                d = doc_map.get(c.document_id)
                images = json.loads(c.image_paths_json) if c.image_paths_json else []
                final_passages.append(
                    RetrievedPassage(
                        chunk_id=c.id,
                        document_id=d.id,
                        document_number=d.document_number,
                        document_title=d.title,
                        revision=d.revision,
                        approval_status=d.approval_status,
                        is_authoritative=authority_by_doc[d.id],
                        page_number=c.page_number,
                        section_title=c.section_title,
                        content=c.content,
                        score=round(score, 4),
                        vector_rank=rank,
                        vector_score=round(score, 4),
                        has_images=c.has_images,
                        image_paths=images,
                        ocr_applied=c.ocr_applied,
                    )
                )

        latency = (time.perf_counter() - start_time) * 1000
        return RetrievalResponse(
            query=query_param.query,
            retrieval_mode=query_param.mode.value,
            total_chunks_searched=total_chunks,
            retrieval_latency_ms=round(latency, 2),
            results=final_passages,
            provider_used=embedding_provider.provider_name,
            fallback_triggered=("fallback" in embedding_provider.provider_name.lower()),
        )

hybrid_retriever = HybridRetriever()
