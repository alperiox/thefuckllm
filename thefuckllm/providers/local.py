"""Local llama.cpp provider."""

from typing import Iterator, Literal

from .base import CompletionResponse, LLMProvider, Message


class LocalProvider(LLMProvider):
    """Provider using local llama.cpp models."""

    def __init__(self, quantization: Literal["q4_k_m", "q8_0"] = "q8_0"):
        self._quantization = quantization
        self._llm = None

    @property
    def name(self) -> str:
        return f"local/{self._quantization}"

    @property
    def is_loaded(self) -> bool:
        return self._llm is not None

    def load(self) -> None:
        """Load the local model."""
        if self._llm is not None:
            return

        from ..models import get_llm

        self._llm = get_llm(self._quantization)

    def unload(self) -> None:
        """Unload the model (clear cache)."""
        from ..models import clear_model_cache

        clear_model_cache()
        self._llm = None

    def _build_chatml_prompt(self, messages: list[Message]) -> str:
        """Build ChatML prompt from messages."""
        from ..prompts import IM_END, IM_START

        parts = []
        for msg in messages:
            parts.append(f"{IM_START}{msg.role}\n{msg.content}\n{IM_END}")

        # Add assistant prefix
        parts.append(f"{IM_START}assistant\n")

        return "".join(parts)

    def complete(
        self,
        messages: list[Message],
        max_tokens: int = 512,
        stop: list[str] | None = None,
        temperature: float = 0.7,
    ) -> CompletionResponse:
        """Generate a completion using llama.cpp."""
        if not self.is_loaded:
            self.load()

        prompt = self._build_chatml_prompt(messages)

        # Add ChatML end token to stop sequences
        stop_tokens = list(stop) if stop else []
        if "<|im_end|>" not in stop_tokens:
            stop_tokens.append("<|im_end|>")

        result = self._llm(
            prompt,
            max_tokens=max_tokens,
            stop=stop_tokens,
            temperature=temperature,
            echo=False,
        )

        return CompletionResponse(
            content=result["choices"][0]["text"].strip(),
            model=self.name,
            usage=result.get("usage"),
        )

    def complete_stream(
        self,
        messages: list[Message],
        max_tokens: int = 512,
        stop: list[str] | None = None,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """Generate a streaming completion."""
        if not self.is_loaded:
            self.load()

        prompt = self._build_chatml_prompt(messages)

        stop_tokens = list(stop) if stop else []
        if "<|im_end|>" not in stop_tokens:
            stop_tokens.append("<|im_end|>")

        for chunk in self._llm(
            prompt,
            max_tokens=max_tokens,
            stop=stop_tokens,
            temperature=temperature,
            echo=False,
            stream=True,
        ):
            text = chunk["choices"][0]["text"]
            if text:
                yield text
