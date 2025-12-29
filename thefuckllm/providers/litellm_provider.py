"""LiteLLM provider for remote APIs."""

from typing import Iterator

from .base import CompletionResponse, LLMProvider, Message


class LiteLLMProvider(LLMProvider):
    """Provider using LiteLLM for remote APIs (OpenAI, Anthropic, Gemini, OpenRouter)."""

    def __init__(self, model: str, api_key: str | None = None):
        """Initialize the LiteLLM provider.

        Args:
            model: Model identifier in LiteLLM format (e.g., "gpt-4o-mini",
                   "anthropic/claude-3-5-sonnet-20241022", "gemini/gemini-1.5-flash")
            api_key: Optional API key (if not set, will use environment variables)
        """
        self._model = model
        self._api_key = api_key
        self._loaded = False

    @property
    def name(self) -> str:
        return f"litellm/{self._model}"

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        """Mark as loaded. LiteLLM handles API key via environment variables."""
        self._loaded = True

    def unload(self) -> None:
        """Mark as unloaded."""
        self._loaded = False

    def _convert_messages(self, messages: list[Message]) -> list[dict]:
        """Convert to OpenAI-style message format."""
        return [{"role": m.role, "content": m.content} for m in messages]

    def complete(
        self,
        messages: list[Message],
        max_tokens: int = 512,
        stop: list[str] | None = None,
        temperature: float = 0.7,
    ) -> CompletionResponse:
        """Generate a completion using LiteLLM."""
        import litellm

        if not self.is_loaded:
            self.load()

        # Build kwargs
        kwargs = {
            "model": self._model,
            "messages": self._convert_messages(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if stop:
            kwargs["stop"] = stop

        if self._api_key:
            kwargs["api_key"] = self._api_key

        response = litellm.completion(**kwargs)

        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return CompletionResponse(
            content=response.choices[0].message.content or "",
            model=self._model,
            usage=usage,
        )

    def complete_stream(
        self,
        messages: list[Message],
        max_tokens: int = 512,
        stop: list[str] | None = None,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """Generate a streaming completion using LiteLLM."""
        import litellm

        if not self.is_loaded:
            self.load()

        kwargs = {
            "model": self._model,
            "messages": self._convert_messages(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        if stop:
            kwargs["stop"] = stop

        if self._api_key:
            kwargs["api_key"] = self._api_key

        response = litellm.completion(**kwargs)

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
