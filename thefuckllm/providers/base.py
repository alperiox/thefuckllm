"""Base class for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator


@dataclass
class Message:
    """A chat message."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class CompletionResponse:
    """Response from a completion request."""

    content: str
    model: str
    usage: dict | None = None  # token counts if available


class LLMProvider(ABC):
    """Abstract base for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        ...

    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """Whether the provider is ready for inference."""
        ...

    @abstractmethod
    def load(self) -> None:
        """Load/initialize the provider (download models if needed)."""
        ...

    @abstractmethod
    def unload(self) -> None:
        """Unload/cleanup resources."""
        ...

    @abstractmethod
    def complete(
        self,
        messages: list[Message],
        max_tokens: int = 512,
        stop: list[str] | None = None,
        temperature: float = 0.7,
    ) -> CompletionResponse:
        """Generate a completion."""
        ...

    def complete_stream(
        self,
        messages: list[Message],
        max_tokens: int = 512,
        stop: list[str] | None = None,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """Generate a streaming completion. Default: non-streaming fallback."""
        response = self.complete(messages, max_tokens, stop, temperature)
        yield response.content
