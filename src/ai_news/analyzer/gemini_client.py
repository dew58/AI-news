"""
Gemini API Client — Phase 2
----------------------------
Thin wrapper around the google-generativeai SDK.

Provides:
  - Configurable API key and model name (from env vars)
  - Bounded retries with exponential backoff for transient errors
  - Token usage tracking per call
  - No retries for permanent errors (invalid key, bad request)

Usage:
    client = GeminiClient()
    text = client.generate("prompt", system_instruction="...")
"""

import logging
import os
import re
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

INITIAL_BACKOFF_SECONDS = 1.0
BACKOFF_MULTIPLIER = 2.0
TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class GeminiError(Exception):
    """Base exception for Gemini client errors."""


class PermanentGeminiError(GeminiError):
    """Non-retryable error (invalid API key, malformed request, etc.)."""


class TransientGeminiError(GeminiError):
    """Retryable error (rate limit, server error, connection issue)."""


class GeminiClient:
    """Thin wrapper around google-generativeai with retries and usage tracking."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
    ):
        self._api_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        self._model_name = model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        self._max_retries = max(1, max_retries)

        self._genai = None
        self._model = None

        self.last_input_tokens: int = 0
        self.last_output_tokens: int = 0
        self.last_duration_ms: float = 0.0

    @property
    def model_name(self) -> str:
        return self._model_name

    def _load_sdk(self):
        """Lazily import and configure the Google Generative AI SDK."""
        if self._genai is not None:
            return

        if not self._api_key:
            raise GeminiError(
                "GEMINI_API_KEY is not set. Add it to your .env file. "
                "Get a free key at https://aistudio.google.com"
            )

        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise GeminiError(
                "google-generativeai package is not installed. "
                "Run: uv add google-generativeai"
            ) from exc

        genai.configure(api_key=self._api_key)
        self._genai = genai
        self._model = genai.GenerativeModel(self._model_name)

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        response_schema: Optional[Any] = None,
    ) -> str:
        """
        Generate content from Gemini with bounded retries.

        Args:
            prompt: The user prompt to send.
            system_instruction: Optional system-level instruction.
            response_schema: Optional schema or Pydantic model for structured output.

        Returns:
            The response text from the model.

        Raises:
            PermanentGeminiError: For non-retryable errors.
            TransientGeminiError: If all retries are exhausted.
        """
        self._load_sdk()

        last_error: Optional[Exception] = None

        # If system_instruction is specified and we have the real SDK, configure model with it
        active_model = self._model
        if system_instruction and self._genai is not None:
            try:
                active_model = self._genai.GenerativeModel(
                    self._model_name,
                    system_instruction=system_instruction,
                )
            except Exception:
                active_model = self._model

        gen_kwargs: dict[str, Any] = {
            "temperature": 0.3,
            "response_mime_type": "application/json",
        }
        if response_schema is not None:
            gen_kwargs["response_schema"] = response_schema

        generation_config = self._genai.GenerationConfig(**gen_kwargs) if self._genai else None

        for attempt in range(1, self._max_retries + 1):
            try:
                start = time.monotonic()

                response = active_model.generate_content(
                    prompt,
                    generation_config=generation_config,
                )

                self.last_duration_ms = (time.monotonic() - start) * 1000

                usage = getattr(response, "usage_metadata", None)
                if usage:
                    self.last_input_tokens = usage.prompt_token_count
                    self.last_output_tokens = usage.candidates_token_count
                    logger.info(
                        "[Gemini] %s | %d in / %d out tokens | %.0f ms",
                        self._model_name,
                        self.last_input_tokens,
                        self.last_output_tokens,
                        self.last_duration_ms,
                    )
                else:
                    self.last_input_tokens = 0
                    self.last_output_tokens = 0

                return response.text

            except Exception as exc:
                last_error = exc
                status_code = self._extract_status_code(exc)

                if status_code is not None and status_code not in TRANSIENT_STATUS_CODES:
                    raise PermanentGeminiError(
                        f"Gemini permanent error (status {status_code}): {exc}"
                    ) from exc

                if attempt < self._max_retries:
                    backoff = INITIAL_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** (attempt - 1))
                    # Check if error message specifies a rate-limit retry delay
                    delay_match = re.search(r"retry\s+(?:in\s+)?(\d+(?:\.\d+)?)s", str(exc), re.IGNORECASE)
                    if delay_match:
                        try:
                            suggested_delay = float(delay_match.group(1))
                            backoff = min(60.0, max(backoff, suggested_delay + 1.0))
                        except ValueError:
                            pass

                    logger.warning(
                        "[Gemini] Attempt %d/%d failed: %s — retrying in %.1fs",
                        attempt,
                        self._max_retries,
                        exc,
                        backoff,
                    )
                    time.sleep(backoff)

        raise TransientGeminiError(
            f"Gemini failed after {self._max_retries} attempts: {last_error}"
        )

    @staticmethod
    def _extract_status_code(exc: Exception) -> Optional[int]:
        """Best-effort extraction of an HTTP status code from a Gemini exception."""
        for attr in ("status_code", "code"):
            val = getattr(exc, attr, None)
            if isinstance(val, int):
                return val
        resp = getattr(exc, "response", None)
        if resp is not None:
            code = getattr(resp, "status_code", None)
            if isinstance(code, int):
                return code
        return None
