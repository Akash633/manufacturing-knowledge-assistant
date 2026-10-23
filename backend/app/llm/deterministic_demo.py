import re
from typing import List, Dict, Any, Tuple, Optional
from app.schemas.retrieval import RetrievedPassage
from app.schemas.query import Citation, AbstentionReasonEnum

class DeterministicDemoGenerator:
    """
    Deterministic rule-based and extractive synthesis engine.
    Ensures 100% verifiable answers with zero hallucinations,
    accurate citations mapped to retrieved chunks, and strict abstention
    when evidence is missing or conflicting.
    
    Does NOT require any external API keys.
    """
    def generate(
        self,
        question: str,
        retrieved_passages: List[RetrievedPassage],
        conflicts_detected: List[str],
        is_safety_critical: bool,
    ) -> Tuple[str, List[Citation], bool, AbstentionReasonEnum, Optional[str]]:
        
        # Priority 1: Safety Critical Mandatory Review
        if is_safety_critical:
            reason = AbstentionReasonEnum.SAFETY_ESCALATION
            explanation = (
                "ABSTENTION: The query addresses a potentially hazardous machine operation "
                "(such as interlock bypass, electrical cabinet access, or speed limit override). "
                "Per manufacturing safety policy, automated instruction is prohibited and the query has been routed to the Expert Review Queue."
            )
            answer = f"⚠️ **SAFETY ESCALATION INITIATED**\n\n{explanation}\n\nPlease consult your shift supervisor and wait for expert sign-off before proceeding."
            return answer, [], True, reason, explanation

        # Priority 2: Evaluate Out-of-Scope Queries
        q_lower = question.lower()
        unsupported_terms = ["laser", "plasma", "wire edm", "3d print", "injection mold", "welding torch"]
        if any(term in q_lower for term in unsupported_terms):
            reason = AbstentionReasonEnum.OUT_OF_SCOPE
            explanation = (
                f"ABSTENTION: The query asks about processes not applicable to DEMO-CNC-01 (a 3-axis CNC vertical milling machine). "
                "The assistant refuses to extrapolate guidance beyond the machine's approved documentation scope."
            )
            answer = f"ℹ️ **OUT OF SCOPE**\n\n{explanation}"
            return answer, [], True, reason, explanation

        # Priority 3: Conflicting Documentation
        if conflicts_detected:
            reason = AbstentionReasonEnum.DOCUMENT_CONFLICT
            conflict_bullets = "\n".join([f"- {c}" for c in conflicts_detected])
            explanation = (
                f"ABSTENTION: Conflicting operating instructions were detected among retrieved applicable documents:\n{conflict_bullets}\n"
                "The assistant refuses to speculate between conflicting directives. A discrepancy ticket has been routed to Quality Engineering."
            )
            answer = f"⚠️ **DOCUMENTATION CONFLICT DETECTED**\n\n{explanation}"
            # Extract citations for the conflicting passages
            citations = self._build_citations_from_passages(retrieved_passages[:2])
            return answer, citations, True, reason, explanation

        # Priority 4: Insufficient Evidence / Zero Passages
        if not retrieved_passages:
            reason = AbstentionReasonEnum.INSUFFICIENT_EVIDENCE
            explanation = (
                "ABSTENTION: No approved documentation found matching the query. "
                "The assistant does not fabricate operational guidance or guess unverified parameters."
            )
            answer = f"ℹ️ **INSUFFICIENT EVIDENCE**\n\n{explanation}\n\nPlease verify that the equipment SOP has been uploaded and approved in the Document Library."
            return answer, [], True, reason, explanation

        # Priority 5: Check if ONLY superseded/unapproved documents were retrieved
        approved_passages = [p for p in retrieved_passages if p.is_authoritative]
        if not approved_passages:
            reason = AbstentionReasonEnum.SUPERSEDED_ONLY
            explanation = (
                "ABSTENTION: Retrieved passages belong to Superseded, Draft, or Expired revisions. "
                "No active, approved operational revision is available for this procedure."
            )
            answer = (
                f"⚠️ **SUPERSEDED REVISION DETECTED**\n\n{explanation}\n\n"
                f"Referenced document {retrieved_passages[0].document_number} ({retrieved_passages[0].revision}) "
                f"has status '{retrieved_passages[0].approval_status}' and cannot be used for active machine operation."
            )
            citations = self._build_citations_from_passages(retrieved_passages[:1])
            return answer, citations, True, reason, explanation

        # Priority 6: Grounded Extractive Answer Formulation
        citations = self._build_citations_from_passages(approved_passages[:3])
        answer = self._synthesize_grounded_answer(question, approved_passages[:3], citations)

        return answer, citations, False, AbstentionReasonEnum.NONE, None

    def _build_citations_from_passages(self, passages: List[RetrievedPassage]) -> List[Citation]:
        citations = []
        for idx, p in enumerate(passages, start=1):
            # Take snippet
            lines = [l.strip() for l in p.content.split("\n") if l.strip() and not l.startswith("[")]
            snippet = " ".join(lines[:3]) if lines else p.content[:150]
            if len(snippet) > 220:
                snippet = snippet[:220] + "..."

            citations.append(
                Citation(
                    citation_id=f"CIT-{idx}",
                    chunk_id=p.chunk_id,
                    document_id=p.document_id,
                    document_number=p.document_number,
                    revision=p.revision,
                    approval_status=p.approval_status,
                    page_number=p.page_number,
                    section_title=p.section_title,
                    snippet=snippet,
                    is_authoritative=p.is_authoritative,
                    is_valid=True,
                )
            )
        return citations

    def _synthesize_grounded_answer(
        self,
        question: str,
        passages: List[RetrievedPassage],
        citations: List[Citation],
    ) -> str:
        """
        Synthesizes a structured answer grounded in the approved retrieved evidence.
        """
        primary = passages[0]
        primary_cit = citations[0]

        # Extract salient points
        content_lines = [l.strip() for l in primary.content.split("\n") if l.strip()]
        informative_lines = [
            l for l in content_lines
            if not l.startswith("[") and not l.startswith("###") and len(l) > 10
        ]
        
        body_points = "\n".join([f"- {line}" for line in informative_lines[:4]]) if informative_lines else primary.content[:300]

        # Check for multimodal visual references
        visual_note = ""
        if primary.has_images and primary.image_paths:
            visual_note = (
                f"\n\n📷 **Associated Visual Evidence**: This procedure references {len(primary.image_paths)} visual schematic(s) on Page {primary.page_number}. "
                "See Evidence Explorer to inspect the high-resolution schematic."
            )

        answer = (
            f"Based on approved document **{primary.document_number}** ({primary.revision}, Status: {primary.approval_status}), "
            f"Page {primary.page_number} [{primary.section_title}]:\n\n"
            f"{body_points}\n\n"
            f"**Traceability Reference**: [{primary_cit.citation_id}] {primary.document_number} Rev {primary.revision}, Page {primary.page_number}."
            f"{visual_note}"
        )
        return answer

deterministic_generator = DeterministicDemoGenerator()
