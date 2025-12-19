"""Inference engine for CLI assistance."""

from .models import get_llm
from .prompts import command_extraction_prompt, ask_prompt, fix_prompt
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
        llm = get_llm()
        prompt = command_extraction_prompt(query)
        result = llm(prompt, max_tokens=10, stop=["<|im_end|>"], echo=False)
        return result["choices"][0]["text"].strip()

    def ask(self, query: str, verbose: bool = False) -> str:
        """Answer a CLI question."""
        # Extract command name
        command = self.extract_command(query)
        if verbose:
            print(f"Detected command: {command}")

        # Retrieve context
        context = self.retriever.get(command, query, verbose=verbose)

        # Generate answer
        llm = get_llm()
        prompt = ask_prompt(query, context)
        result = llm(prompt, max_tokens=512, stop=["<|im_end|>"], echo=False)
        return result["choices"][0]["text"].strip()

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
        llm = get_llm()
        prompt = fix_prompt(failed_command, exit_code, stdout, stderr, context)
        result = llm(prompt, max_tokens=256, stop=["<|im_end|>", "\n\n"], echo=False)
        return result["choices"][0]["text"].strip()


# Singleton instance
_engine: InferenceEngine | None = None


def get_engine() -> InferenceEngine:
    """Get the singleton engine instance."""
    global _engine
    if _engine is None:
        _engine = InferenceEngine()
    return _engine
