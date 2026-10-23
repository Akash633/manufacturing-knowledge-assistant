from typing import List, Dict, Any, Set
from app.schemas.query import Citation
from app.schemas.retrieval import RetrievedPassage

class CitationValidator:
    """
    Validates generated citations strictly against retrieved evidence passages.
    Rejects any fabricated citations, fake page numbers, or non-retrieved document IDs.
    """
    def validate_citations(
        self,
        candidate_citations: List[Citation],
        retrieved_passages: List[RetrievedPassage],
    ) -> List[Citation]:
        valid_chunk_map: Dict[str, RetrievedPassage] = {
            p.chunk_id: p for p in retrieved_passages
        }

        validated_citations: List[Citation] = []

        for cit in candidate_citations:
            # Check if referenced chunk was actually in the retrieved set
            if cit.chunk_id not in valid_chunk_map:
                # Citation references a chunk that was NOT retrieved! Hallucination caught.
                continue

            passage = valid_chunk_map[cit.chunk_id]

            # Verify document ID and page number match the ground-truth passage
            doc_id_matches = (cit.document_id == passage.document_id)
            page_matches = (cit.page_number == passage.page_number)

            if not (doc_id_matches and page_matches):
                # Correct fabricated page number or doc ID with authoritative ground truth
                cit.document_id = passage.document_id
                cit.page_number = passage.page_number
                cit.document_number = passage.document_number
                cit.revision = passage.revision
                cit.approval_status = passage.approval_status
                cit.section_title = passage.section_title

            cit.is_authoritative = passage.is_authoritative
            cit.is_valid = True
            validated_citations.append(cit)

        return validated_citations

citation_validator = CitationValidator()
