"""Modular LLM provider abstraction and structured inference types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class ProviderUsage:
    """Token consumption and execution telemetry."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0


@dataclass
class StructuredOutputResult(Generic[T]):
    """Validated structured LLM result with provider provenance."""

    data: T
    provider: str
    model: str
    raw_response: str
    usage: ProviderUsage
    fallback_used: bool = False


@dataclass
class TextOutputResult:
    """Unstructured text LLM result with provider provenance."""

    text: str
    provider: str
    model: str
    usage: ProviderUsage
    fallback_used: bool = False


class LLMProvider(ABC):
    """Abstract protocol for an inference provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'groq', 'nvidia')."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Active model name."""

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str | None = None,
        timeout: float = 30.0,
    ) -> StructuredOutputResult[T]:
        """Generate validated Pydantic structured output."""

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        timeout: float = 30.0,
    ) -> TextOutputResult:
        """Generate free-form text output."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check provider reachability and credential validity."""
