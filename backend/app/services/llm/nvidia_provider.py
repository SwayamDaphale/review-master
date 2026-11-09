"""NVIDIA NIM cloud inference provider adapter using standard OpenAI REST conventions."""

import json
import logging
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.services.llm.base import (
    LLMProvider,
    ProviderUsage,
    StructuredOutputResult,
    TextOutputResult,
)

logger = logging.getLogger("review_master.llm.nvidia")
T = TypeVar("T", bound=BaseModel)

NVIDIA_API_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"


class NvidiaProvider(LLMProvider):
    """NVIDIA NIM API provider adapter."""

    def __init__(self, api_key: str | None, model: str = "meta/llama-3.3-70b-instruct"):
        self._api_key = api_key
        self._model = model

    @property
    def name(self) -> str:
        return "nvidia"

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
        """Invoke NVIDIA NIM with JSON response formatting."""
        if not self._api_key:
            raise ValueError("NVIDIA API key not configured.")

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
            resp = await client.post(NVIDIA_API_ENDPOINT, json=payload, headers=headers)
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
                logger.error("NVIDIA NIM output schema validation failed: %s", e)
                raise ValueError(
                    f"NVIDIA NIM response did not conform to schema: {e}"
                ) from e

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
        """Invoke NVIDIA NIM for text generation."""
        if not self._api_key:
            raise ValueError("NVIDIA API key not configured.")

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
            resp = await client.post(NVIDIA_API_ENDPOINT, json=payload, headers=headers)
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
        """Probe NVIDIA NIM API availability."""
        if not self._api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://integrate.api.nvidia.com/v1/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                return resp.status_code == 200
        except (httpx.HTTPError, OSError) as e:
            logger.debug("NVIDIA health check failed: %s", e)
            return False
