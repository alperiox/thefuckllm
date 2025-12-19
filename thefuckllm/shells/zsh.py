"""Zsh shell integration."""

from .base import Shell


class Zsh(Shell):
    """Zsh shell hook implementation."""

    @property
    def name(self) -> str:
        return "zsh"

    def get_init_script(self, alias: str = "fuck") -> str:
        """Generate zsh initialization script.

        Uses zsh hooks: preexec and precmd.
        Reads terminal output from script log file if available.
        """
        return f'''
# thefuckllm shell integration for zsh

# Capture command before execution
__thefuckllm_preexec() {{
    export __THEFUCKLLM_LAST_CMD="$1"
}}

# Capture exit code after execution
__thefuckllm_precmd() {{
    export __THEFUCKLLM_EXIT_CODE="$?"
}}

# Register hooks
autoload -Uz add-zsh-hook
add-zsh-hook preexec __thefuckllm_preexec
add-zsh-hook precmd __thefuckllm_precmd

# The fix command function
{alias}() {{
    local last_cmd="${{__THEFUCKLLM_LAST_CMD:-$(fc -ln -1)}}"
    local exit_code="${{__THEFUCKLLM_EXIT_CODE:-1}}"

    if [[ -z "$last_cmd" ]]; then
        echo "No previous command found" >&2
        return 1
    fi

    # Get the fix suggestion (CLI will read from SCRIPT_LOG_FILE if set)
    local fix_cmd
    fix_cmd=$(tfllm fix-internal --command "$last_cmd" --exit-code "$exit_code" 2>/dev/null)

    if [[ -z "$fix_cmd" ]]; then
        echo "No fix suggested" >&2
        return 1
    fi

    echo "Suggested fix: $fix_cmd"

    # Check for execute flag
    if [[ "$1" == "-e" ]] || [[ "$1" == "--execute" ]]; then
        read -q "REPLY?Execute? [y/N] "
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            eval "$fix_cmd"
        fi
    fi
}}
'''
