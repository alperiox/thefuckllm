"""Base class for shell integrations."""

from abc import ABC, abstractmethod


class Shell(ABC):
    """Abstract base for shell hook implementations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Shell name (e.g., 'bash', 'zsh', 'fish')."""
        ...

    @abstractmethod
    def get_init_script(self, alias: str = "fuck") -> str:
        """Generate shell initialization script.

        The script should:
        1. Define a function/alias that captures the last command
        2. Capture exit code, stdout, and stderr
        3. Call thefuckllm fix with the captured data
        4. Optionally execute the suggested fix
        """
        ...


def get_shell(shell_name: str) -> Shell:
    """Factory to get shell implementation."""
    from .bash import Bash
    from .zsh import Zsh
    from .fish import Fish

    shells: dict[str, type[Shell]] = {
        "bash": Bash,
        "zsh": Zsh,
        "fish": Fish,
    }

    if shell_name not in shells:
        raise ValueError(f"Unsupported shell: {shell_name}. Supported: {list(shells.keys())}")

    return shells[shell_name]()
