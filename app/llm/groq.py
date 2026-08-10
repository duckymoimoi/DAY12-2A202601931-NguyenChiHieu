"""Small Groq Chat Completions client built on the existing httpx dependency."""

from __future__ import annotations

from typing import Any

import httpx


class LLMProviderError(RuntimeError):
    """A sanitized provider error safe to log or return as fallback metadata."""


class GroqProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_tokens: int,
        temperature: float,
        reasoning_effort: str,
        include_reasoning: bool,
        input_price_per_million: float,
        output_price_per_million: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise LLMProviderError("GROQ_API_KEY is not configured")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.include_reasoning = include_reasoning
        self.input_price_per_million = input_price_per_million
        self.output_price_per_million = output_price_per_million
        self.transport = transport

    def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        "reasoning_effort": self.reasoning_effort,
                        "include_reasoning": self.include_reasoning,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"Groq returned HTTP {exc.response.status_code}"
            ) from exc
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("Groq request failed") from exc

        try:
            answer = payload["choices"][0]["message"]["content"].strip()
            usage = payload.get("usage") or {}
            tokens_in = int(usage.get("prompt_tokens", 0))
            tokens_out = int(usage.get("completion_tokens", 0))
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
            raise LLMProviderError("Groq returned an unexpected response") from exc

        if not answer:
            raise LLMProviderError("Groq returned an empty answer")

        cost = (
            tokens_in * self.input_price_per_million
            + tokens_out * self.output_price_per_million
        ) / 1_000_000
        return {
            "answer": answer,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": round(cost, 8),
            "provider": "groq",
            "model": self.model,
        }
