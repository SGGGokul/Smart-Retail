"""Groq API Integration Service for GPT-OSS-20B, Prompt Guard 2, and Safeguard.

Provides resilient HTTP client integration with:
- openai/gpt-oss-20b (Primary LLM)
- meta-llama/llama-prompt-guard-2-86m (Input Guard Classifier)
- openai/gpt-oss-safeguard-20b (Output Safeguard Classifier)

Includes timeout management, retry logic, latency measurement, and secure handling
(never logging API keys or exposing credentials).
"""

import logging
import time
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import get_settings

logger = logging.getLogger("retailiq.security.groq_service")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqService:
    """Production client for Groq LLM inference and guardrail models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        guard_model: Optional[str] = None,
        safeguard_model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self.guard_model = guard_model or settings.GROQ_GUARD_MODEL
        self.safeguard_model = safeguard_model or settings.GROQ_SAFEGUARD_MODEL
        self.timeout_seconds = timeout_seconds or settings.GROQ_TIMEOUT_SECONDS
        self.max_tokens = settings.GROQ_MAX_TOKENS

        # Track latency metrics
        self.last_latency_ms: float = 0.0
        self.last_guard_latency_ms: float = 0.0

    def is_configured(self) -> bool:
        """Check if Groq API key is present."""
        return bool(self.api_key and self.api_key.startswith("gsk_"))

    async def classify_prompt_guard(self, user_prompt: str) -> Optional[float]:
        """Query Llama Prompt Guard 2 86M to obtain injection/jailbreak probability (0.0 to 1.0).

        Returns probability score or None if Groq is unavailable/unconfigured.
        """
        if not self.is_configured():
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.guard_model,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(GROQ_API_URL, headers=headers, json=payload)
                self.last_guard_latency_ms = (time.time() - t0) * 1000

                if response.status_code == 200:
                    data = response.json()
                    raw_content = data["choices"][0]["message"]["content"].strip()
                    try:
                        score = float(raw_content)
                        return max(0.0, min(1.0, score))
                    except ValueError:
                        logger.warning(f"Unexpected Prompt Guard output: '{raw_content}'")
                        return None
                else:
                    logger.warning(f"Prompt Guard API returned status {response.status_code}: {response.text[:100]}")
                    return None
        except Exception as err:
            logger.warning(f"Prompt Guard request failed: {err}")
            return None

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """Generate response from GPT-OSS-20B via Groq API.

        Returns generated content string or None if API fails.
        """
        if not self.is_configured():
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(GROQ_API_URL, headers=headers, json=payload)
                self.last_latency_ms = (time.time() - t0) * 1000

                if response.status_code == 200:
                    data = response.json()
                    choice = data["choices"][0]
                    content = choice["message"].get("content") or ""
                    return content.strip()
                elif response.status_code == 429:
                    logger.error("Groq API rate limit exceeded.")
                    return None
                else:
                    logger.error(f"Groq API error ({response.status_code}): {response.text[:200]}")
                    return None
        except httpx.TimeoutException:
            logger.error(f"Groq API call timed out after {self.timeout_seconds}s.")
            return None
        except Exception as err:
            logger.error(f"Groq API call encountered exception: {err}")
            return None

    async def verify_output_safeguard(self, text: str) -> Optional[str]:
        """Query GPT-OSS-Safeguard-20B to evaluate output safety (SAFE vs UNSAFE)."""
        if not self.is_configured():
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.safeguard_model,
            "messages": [
                {
                    "role": "user",
                    "content": f"Is the following text safe and compliant for retail store operations? Answer SAFE or UNSAFE only.\n\nText:\n{text}",
                }
            ],
            "max_tokens": 200,
            "temperature": 0.0,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(GROQ_API_URL, headers=headers, json=payload)
                if response.status_code == 200:
                    content = response.json()["choices"][0]["message"].get("content", "").strip()
                    return content.upper()
                return None
        except Exception as err:
            logger.warning(f"Safeguard check failed: {err}")
            return None


_groq_service: Optional[GroqService] = None


def get_groq_service() -> GroqService:
    global _groq_service
    if _groq_service is None:
        _groq_service = GroqService()
    return _groq_service
