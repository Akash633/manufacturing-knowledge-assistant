from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
from app.core.config import settings
from app.core.logging import logger
from app.schemas.retrieval import RetrievedPassage
from app.schemas.query import Citation, AbstentionReasonEnum
from app.llm.deterministic_demo import deterministic_generator

class BaseLLMProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def generate_grounded_answer(
        self,
        question: str,
        retrieved_passages: List[RetrievedPassage],
        conflicts_detected: List[str],
        is_safety_critical: bool,
    ) -> Tuple[str, List[Citation], bool, AbstentionReasonEnum, Optional[str]]:
        pass


class DeterministicDemoProvider(BaseLLMProvider):
    @property
    def provider_name(self) -> str:
        return "deterministic_demo_engine"

    def generate_grounded_answer(
        self,
        question: str,
        retrieved_passages: List[RetrievedPassage],
        conflicts_detected: List[str],
        is_safety_critical: bool,
    ) -> Tuple[str, List[Citation], bool, AbstentionReasonEnum, Optional[str]]:
        return deterministic_generator.generate(
            question=question,
            retrieved_passages=retrieved_passages,
            conflicts_detected=conflicts_detected,
            is_safety_critical=is_safety_critical,
        )


class OpenAILLMProvider(BaseLLMProvider):
    """
    OpenAI provider with strict manufacturing grounding prompt.
    Automatically falls back to deterministic generator if API key is unset or error occurs.
    """
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.fallback = DeterministicDemoProvider()

    @property
    def provider_name(self) -> str:
        if self.api_key:
            return f"openai ({self.model})"
        return "deterministic_demo_engine (fallback)"

    def generate_grounded_answer(
        self,
        question: str,
        retrieved_passages: List[RetrievedPassage],
        conflicts_detected: List[str],
        is_safety_critical: bool,
    ) -> Tuple[str, List[Citation], bool, AbstentionReasonEnum, Optional[str]]:
        # Enforce deterministic safety and conflict guardrails first
        if is_safety_critical or conflicts_detected or not retrieved_passages:
            return self.fallback.generate_grounded_answer(
                question, retrieved_passages, conflicts_detected, is_safety_critical
            )

        if not self.api_key:
            return self.fallback.generate_grounded_answer(
                question, retrieved_passages, conflicts_detected, is_safety_critical
            )

        try:
            import httpx
            # Call OpenAI chat completion endpoint
            evidence_blocks = []
            for idx, p in enumerate(retrieved_passages[:3], start=1):
                evidence_blocks.append(
                    f"[Evidence {idx}] Doc: {p.document_number} (Rev: {p.revision}, Status: {p.approval_status}), "
                    f"Page {p.page_number}, Section: {p.section_title}\n{p.content}"
                )
            evidence_str = "\n\n".join(evidence_blocks)

            system_prompt = (
                "You are an industrial manufacturing operations assistant. "
                "Answer the shop-floor question STRICTLY based on the provided approved evidence passages. "
                "Never extrapolate safety parameters or invent values. Cite the Evidence index, document number, and page number for every assertion."
            )
            user_prompt = f"RETRIEVED EVIDENCE:\n{evidence_str}\n\nQUESTION: {question}"

            # If user or environment has configured an endpoint
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.0,
                },
                timeout=15.0,
            )
            if response.status_code == 200:
                answer_text = response.json()["choices"][0]["message"]["content"]
                citations = self.fallback.generate_grounded_answer(
                    question, retrieved_passages, conflicts_detected, is_safety_critical
                )[1]
                return answer_text, citations, False, AbstentionReasonEnum.NONE, None
            else:
                logger.warning(f"OpenAI API error {response.status_code}. Using deterministic fallback.")
        except Exception as e:
            logger.warning(f"OpenAI call failed ({e}). Using deterministic fallback.")

        return self.fallback.generate_grounded_answer(
            question, retrieved_passages, conflicts_detected, is_safety_critical
        )


def get_llm_provider() -> BaseLLMProvider:
    if settings.LLM_PROVIDER.lower() == "openai" and settings.OPENAI_API_KEY:
        return OpenAILLMProvider(settings.OPENAI_API_KEY, settings.OPENAI_MODEL)
    return DeterministicDemoProvider()

llm_provider = get_llm_provider()
