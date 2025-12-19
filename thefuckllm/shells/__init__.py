"""Shell integration for thefuckllm."""

from .base import Shell, get_shell
from .bash import Bash
from .zsh import Zsh
from .fish import Fish

__all__ = ["Shell", "get_shell", "Bash", "Zsh", "Fish"]
