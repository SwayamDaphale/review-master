"""Inference orchestrator managing Groq primary, NVIDIA NIM fallback, and error handling."""

import asyncio
import logging
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.services.llm.base import (
    LLMProvider,
    StructuredOutputResult,
    TextOutputResult,
)
from app.services.llm.groq_provider import GroqProvider
from app.services.llm.nvidia_provider import NvidiaProvider

logger = logging.getLogger("review_master.llm.orchestrator")
T = TypeVar("T", bound=BaseModel)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class InferenceOrchestrator:
    """Orchestrates LLM inference with Groq primary and NVIDIA NIM failover."""

    def __init__(
        self,
        primary_provider: LLMProvider | None = None,
        fallback_provider: LLMProvider | None = None,
        fallback_enabled: bool | None = None,
        max_retries: int | None = None,
        timeout: float | None = None,
    ):
        self.primary: LLMProvider = primary_provider or GroqProvider(
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
        )
        self.fallback: LLMProvider = fallback_provider or NvidiaProvider(
            api_key=settings.NVIDIA_API_KEY,
            model=settings.NVIDIA_MODEL,
        )
        self.fallback_enabled: bool = (
            fallback_enabled
            if fallback_enabled is not None
            else settings.LLM_FALLBACK_ENABLED
        )
        self.max_retries: int = (
            max_retries if max_retries is not None else settings.LLM_MAX_RETRIES
        )
        self.timeout: float = (
            timeout if timeout is not None else settings.LLM_TIMEOUT_SECONDS
        )

    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str | None = None,
    ) -> StructuredOutputResult[T]:
        """Execute structured generation attempting primary then falling back if eligible."""
        try:
            return await self._execute_with_retry(
                self.primary,
                lambda p: p.generate_structured(
                    prompt, schema, system_prompt, timeout=self.timeout
                ),
            )
        except Exception as primary_err:
            if not self._is_eligible_for_failover(primary_err):
                logger.error(
                    "Primary provider (%s) encountered non-retryable error: %s",
                    self.primary.name,
                    primary_err,
                )
                raise

            if not self.fallback_enabled:
                logger.warning("Primary provider failed and fallback is disabled.")
                raise

            logger.warning(
                "Primary provider (%s) failed with eligible error (%s). Engaging fallback provider (%s)...",
                self.primary.name,
                primary_err,
                self.fallback.name,
            )

            try:
                result = await self._execute_with_retry(
                    self.fallback,
                    lambda p: p.generate_structured(
                        prompt, schema, system_prompt, timeout=self.timeout
                    ),
                )
                result.fallback_used = True
                return result
            except Exception as fallback_err:
                logger.error(
                    "Both primary and fallback LLM providers failed: %s", fallback_err
                )
                raise RuntimeError(
                    f"All LLM inference providers failed. Primary: {primary_err}; Fallback: {fallback_err}"
                ) from fallback_err

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> TextOutputResult:
        """Execute text generation with failover."""
        try:
            return await self._execute_with_retry(
                self.primary,
                lambda p: p.generate_text(prompt, system_prompt, timeout=self.timeout),
            )
        except Exception as primary_err:
            if not self._is_eligible_for_failover(primary_err):
                raise

            if not self.fallback_enabled:
                raise

            logger.warning(
                "Primary provider (%s) failed with eligible error (%s). Engaging fallback provider (%s)...",
                self.primary.name,
                primary_err,
                self.fallback.name,
            )

            result = await self._execute_with_retry(
                self.fallback,
                lambda p: p.generate_text(prompt, system_prompt, timeout=self.timeout),
            )
            result.fallback_used = True
            return result

    async def _execute_with_retry(self, provider: LLMProvider, call_fn) -> Any:
        """Execute provider call with bounded exponential retries on transient errors."""
        last_exception: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await call_fn(provider)
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_exception = e
                logger.warning(
                    "[%s] Network/Timeout error on attempt %d/%d: %s",
                    provider.name,
                    attempt,
                    self.max_retries,
                    e,
                )
            except httpx.HTTPStatusError as e:
                last_exception = e
                if e.response.status_code in RETRYABLE_STATUS_CODES:
                    logger.warning(
                        "[%s] Retryable HTTP %d on attempt %d/%d",
                        provider.name,
                        e.response.status_code,
                        attempt,
                        self.max_retries,
                    )
                else:
                    # Terminal client-side error (400, 401, 403, 404, 422) -> do not retry
                    raise
            except ValueError:
                # Schema parsing or validation failure -> terminal for this prompt
                raise

            if attempt < self.max_retries:
                backoff_seconds = 0.5 * (2 ** (attempt - 1))
                await asyncio.sleep(backoff_seconds)

        if last_exception:
            raise last_exception

    def _is_eligible_for_failover(self, exc: Exception) -> bool:
        """Determine if an exception warrants failover to the backup provider."""
        if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in RETRYABLE_STATUS_CODES
        return False
