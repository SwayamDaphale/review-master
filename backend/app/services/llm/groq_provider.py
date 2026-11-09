"""Groq cloud inference provider adapter using standard OpenAI REST conventions."""

import json
import logging
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.services.llm.base import (
    LLMProvider,
    ProviderUsage,
    StructuredOutputResult,
    TextOutputResult,
)

logger = logging.getLogger("review_master.llm.groq")
T = TypeVar("T", bound=BaseModel)

GROQ_API_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(LLMProvider):
    """Groq Cloud API provider adapter."""

    def __init__(self, api_key: str | None, model: str = "llama-3.3-70b-versatile"):
        self._api_key = api_key
        self._model = model

    @property
    def name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model

    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str | None = None,
        timeout: float = 30.0,
    ) -> StructuredOutputResult[T]:
        """Invoke Groq with JSON mode and validate against Pydantic schema."""
        if (
            not self._api_key or self._api_key in ("mock", "dev", "test")
        ) and settings.APP_ENV == "development":
            mock_data = {
                "sentiment": "positive",
                "sentiment_confidence": 0.95,
                "aspects": [
                    {
                        "aspect_key": "battery",
                        "polarity": "positive",
                        "claim": "Battery life lasts two full days.",
                        "raw_quote": "battery lasts two full days",
                        "confidence": 0.95,
                    }
                ],
                "pros_cons": [
                    {
                        "item_type": "pro",
                        "text": "Excellent battery performance",
                        "aspect_key": "battery",
                        "confidence": 0.95,
                        "source_reference": "lasts two full days",
                    }
                ],
                "pros": ["Excellent battery performance"],
                "cons": [],
            }
            try:
                validated_data = schema.model_validate(mock_data)
            except Exception:  # noqa: BLE001
                validated_data = schema.model_validate({})
            return StructuredOutputResult(
                data=validated_data,
                provider="groq",
                model=self._model,
                raw_response=json.dumps(mock_data),
                usage=ProviderUsage(
                    prompt_tokens=50,
                    completion_tokens=25,
                    total_tokens=75,
                    latency_ms=10.0,
                ),
                fallback_used=False,
            )

        if not self._api_key:
            raise ValueError("Groq API key not configured.")

        schema_json_str = json.dumps(schema.model_json_schema())
        sys_instruction = (
            (
                system_prompt
                or "You are an expert review intelligence analysis assistant."
            )
            + f"\nYou MUST reply ONLY with valid JSON conforming strictly to this JSON Schema:\n{schema_json_str}"
        )

        messages = [
            {"role": "system", "content": sys_instruction},
            {"role": "user", "content": prompt},
        ]

        payload = {
            "model": self._model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(GROQ_API_ENDPOINT, json=payload, headers=headers)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if resp.status_code != 200:
                resp.raise_for_status()

            body = resp.json()
            raw_content = body["choices"][0]["message"]["content"]
            usage_data = body.get("usage", {})

            usage = ProviderUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
                latency_ms=latency_ms,
            )

            try:
                parsed_json = json.loads(raw_content)
                validated_data = schema.model_validate(parsed_json)
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error("Groq output schema validation failed: %s", e)
                raise ValueError(f"Groq response did not conform to schema: {e}") from e

            return StructuredOutputResult(
                data=validated_data,
                provider=self.name,
                model=self._model,
                raw_response=raw_content,
                usage=usage,
            )

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        timeout: float = 30.0,
    ) -> TextOutputResult:
        """Invoke Groq for free-form text completion."""
        if (
            not self._api_key or self._api_key in ("mock", "dev", "test")
        ) and settings.APP_ENV == "development":
            return TextOutputResult(
                text="Development mock generated summary.",
                provider="groq",
                model=self._model,
                usage=ProviderUsage(
                    prompt_tokens=10,
                    completion_tokens=10,
                    total_tokens=20,
                    latency_ms=5.0,
                ),
                fallback_used=False,
            )

        if not self._api_key:
            raise ValueError("Groq API key not configured.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(GROQ_API_ENDPOINT, json=payload, headers=headers)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if resp.status_code != 200:
                resp.raise_for_status()

            body = resp.json()
            raw_content = body["choices"][0]["message"]["content"]
            usage_data = body.get("usage", {})

            usage = ProviderUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
                latency_ms=latency_ms,
            )

            return TextOutputResult(
                text=raw_content,
                provider=self.name,
                model=self._model,
                usage=usage,
            )

    async def health_check(self) -> bool:
        """Probe Groq API availability."""
        if not self._api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                return resp.status_code == 200
        except (httpx.HTTPError, OSError) as e:
            logger.debug("Groq health check failed: %s", e)
            return False
