from abc import ABC, abstractmethod
import re
from threading import local
from typing import List, Optional, Tuple

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
    def __init__(self, display_name: str = "deterministic_demo_engine"):
        self.display_name = display_name

    @property
    def provider_name(self) -> str:
        return self.display_name

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
    """OpenAI provider with deterministic, explicitly labelled fallback behavior."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = self._validated_api_key(api_key or settings.OPENAI_API_KEY)
        self.model = model
        self.fallback = DeterministicDemoProvider()
        self._call_state = local()

    @staticmethod
    def _validated_api_key(api_key: Optional[str]) -> Optional[str]:
        if not isinstance(api_key, str):
            return None
        key = api_key.strip()
        normalized = key.lower()
        if (
            not key
            or normalized in {"none", "null", "placeholder", "changeme", "******", "..."}
            or "..." in normalized
        ):
            return None
        if re.fullmatch(r"(?:\*+|x+|<[^>]+>)", normalized):
            return None
        if normalized.startswith(("your-", "your_")):
            return None
        return key

    @property
    def provider_name(self) -> str:
        return getattr(
            self._call_state,
            "provider_name",
            f"openai ({self.model}; request not yet made)",
        )

    def _fallback_result(
        self,
        question: str,
        retrieved_passages: List[RetrievedPassage],
        conflicts_detected: List[str],
        is_safety_critical: bool,
        reason: str,
    ) -> Tuple[str, List[Citation], bool, AbstentionReasonEnum, Optional[str]]:
        self._call_state.provider_name = f"deterministic_demo_engine (OpenAI fallback: {reason})"
        return self.fallback.generate_grounded_answer(
            question, retrieved_passages, conflicts_detected, is_safety_critical
        )

    def generate_grounded_answer(
        self,
        question: str,
        retrieved_passages: List[RetrievedPassage],
        conflicts_detected: List[str],
        is_safety_critical: bool,
    ) -> Tuple[str, List[Citation], bool, AbstentionReasonEnum, Optional[str]]:
        if is_safety_critical or conflicts_detected or not retrieved_passages:
            return self._fallback_result(
                question, retrieved_passages, conflicts_detected, is_safety_critical,
                "safety, conflict, or missing evidence",
            )

        if not self.api_key:
            return self._fallback_result(
                question, retrieved_passages, conflicts_detected, is_safety_critical,
                "missing or placeholder API key",
            )

        import httpx

        try:
            evidence_blocks = []
            for idx, passage in enumerate(retrieved_passages[:3], start=1):
                evidence_blocks.append(
                    f"[Evidence {idx}] Doc: {passage.document_number} "
                    f"(Rev: {passage.revision}, Status: {passage.approval_status}), "
                    f"Page {passage.page_number}, Section: {passage.section_title}\n{passage.content}"
                )
            evidence_str = "\n\n".join(evidence_blocks)

            system_prompt = (
                "You are an industrial manufacturing operations assistant. "
                "Answer the shop-floor question STRICTLY based on the provided approved evidence passages. "
                "Never extrapolate safety parameters or invent values. Cite the Evidence index, document number, "
                "and page number for every assertion."
            )
            user_prompt = f"RETRIEVED EVIDENCE:\n{evidence_str}\n\nQUESTION: {question}"

            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": "Bearer " + self.api_key},
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
            if response.status_code != 200:
                logger.warning(f"OpenAI API error {response.status_code}. Using deterministic fallback.")
                return self._fallback_result(
                    question, retrieved_passages, conflicts_detected, is_safety_critical,
                    "request failed",
                )

            answer_text = response.json()["choices"][0]["message"]["content"]
            if not isinstance(answer_text, str) or not answer_text.strip():
                logger.warning("OpenAI returned an empty or malformed answer. Using deterministic fallback.")
                return self._fallback_result(
                    question, retrieved_passages, conflicts_detected, is_safety_critical,
                    "invalid OpenAI response",
                )

            citations = self.fallback.generate_grounded_answer(
                question, retrieved_passages, conflicts_detected, is_safety_critical
            )[1]
            self._call_state.provider_name = f"openai ({self.model})"
            return answer_text, citations, False, AbstentionReasonEnum.NONE, None
        except httpx.HTTPError as exc:
            logger.warning(f"OpenAI request failed ({type(exc).__name__}). Using deterministic fallback.")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning(f"OpenAI response was invalid ({type(exc).__name__}). Using deterministic fallback.")

        return self._fallback_result(
            question, retrieved_passages, conflicts_detected, is_safety_critical,
            "request failed",
        )


def get_llm_provider() -> BaseLLMProvider:
    if settings.LLM_PROVIDER.lower() == "openai":
        provider = OpenAILLMProvider(settings.OPENAI_API_KEY, settings.OPENAI_MODEL)
        if provider.api_key:
            return provider
        logger.warning(
            "OpenAI provider requested but OPENAI_API_KEY is missing or a placeholder; "
            "using deterministic demo fallback."
        )
        return DeterministicDemoProvider(
            display_name="deterministic_demo_engine (OpenAI unavailable: missing or placeholder API key)"
        )
    return DeterministicDemoProvider()


llm_provider = get_llm_provider()
