"""Inference engine for CLI assistance."""

from .prompts import (
    CLI_EXPERT_SYSTEM,
    COMMAND_EXTRACTOR_SYSTEM,
    FIX_COMMAND_SYSTEM,
)
from .providers import Message, get_provider
from .retriever import ContextRetriever


class InferenceEngine:
    """Orchestrates retrieval and LLM inference."""

    def __init__(self):
        self._retriever: ContextRetriever | None = None

    @property
    def retriever(self) -> ContextRetriever:
        """Lazy load retriever."""
        if self._retriever is None:
            self._retriever = ContextRetriever()
        return self._retriever

    def extract_command(self, query: str) -> str:
        """Extract CLI tool name from query."""
        provider = get_provider()
        messages = [
            Message(role="system", content=COMMAND_EXTRACTOR_SYSTEM),
            Message(role="user", content=f"Extract the CLI tool name from: {query}"),
        ]
        response = provider.complete(messages, max_tokens=10)
        return response.content.strip()

    def ask(self, query: str, verbose: bool = False) -> str:
        """Answer a CLI question."""
        # Extract command name
        command = self.extract_command(query)
        if verbose:
            print(f"Detected command: {command}")

        # Retrieve context
        context = self.retriever.get(command, query, verbose=verbose)

        # Generate answer
        provider = get_provider()
        context_text = "\n\n".join(context)
        messages = [
            Message(role="system", content=CLI_EXPERT_SYSTEM),
            Message(role="user", content=f"Context:\n{context_text}\n\nQuestion: {query}"),
        ]
        response = provider.complete(messages, max_tokens=512)
        return response.content.strip()

    def fix(
        self,
        failed_command: str,
        exit_code: int,
        stdout: str = "",
        stderr: str = "",
        verbose: bool = False,
    ) -> str:
        """Suggest a fix for a failed command."""
        # Try to extract command for context
        command = failed_command.split()[0] if failed_command else ""

        # Attempt to get relevant context
        context = None
        if command:
            try:
                context = self.retriever.get(
                    command,
                    f"fix error: {stderr[:200]}",
                    top_k=2,
                    verbose=verbose,
                )
            except Exception:
                pass  # Proceed without context if retrieval fails

        # Generate fix
        provider = get_provider()
        user_msg = f"Fix this command: {failed_command}"
        if stderr:
            user_msg += f"\nError: {stderr[:500]}"

        messages = [
            Message(role="system", content=FIX_COMMAND_SYSTEM),
            Message(role="user", content=user_msg),
        ]
        response = provider.complete(messages, max_tokens=256, stop=["\n\n"])
        return response.content.strip()


# Singleton instance
_engine: InferenceEngine | None = None


def get_engine() -> InferenceEngine:
    """Get the singleton engine instance."""
    global _engine
    if _engine is None:
        _engine = InferenceEngine()
    return _engine
