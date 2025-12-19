"""Bash shell integration."""

from .base import Shell


class Bash(Shell):
    """Bash shell hook implementation."""

    @property
    def name(self) -> str:
        return "bash"

    def get_init_script(self, alias: str = "fuck") -> str:
        """Generate bash initialization script.

        Strategy:
        - Use DEBUG trap to capture command before execution
        - Use PROMPT_COMMAND to capture exit code after execution
        - Re-run failed command to capture stderr for the LLM
        """
        return f'''
# thefuckllm shell integration for bash

# Capture command before execution
__thefuckllm_preexec() {{
    # Store the command before execution
    export __THEFUCKLLM_LAST_CMD="$1"
}}

# Capture exit code after execution
__thefuckllm_precmd() {{
    # Capture exit code immediately
    export __THEFUCKLLM_EXIT_CODE="$?"
}}

# Enable command capture via DEBUG trap
__thefuckllm_debug_trap() {{
    [ -n "$COMP_LINE" ] && return  # Skip during completion
    [ "$BASH_COMMAND" = "$PROMPT_COMMAND" ] && return  # Skip prompt command itself
    __thefuckllm_preexec "$BASH_COMMAND"
}}

trap '__thefuckllm_debug_trap' DEBUG
PROMPT_COMMAND="__thefuckllm_precmd;${{PROMPT_COMMAND}}"

# The fix command function
{alias}() {{
    local last_cmd="${{__THEFUCKLLM_LAST_CMD:-$(fc -ln -1 | sed 's/^[[:space:]]*//')}}"
    local exit_code="${{__THEFUCKLLM_EXIT_CODE:-1}}"

    if [ -z "$last_cmd" ]; then
        echo "No previous command found" >&2
        return 1
    fi

    # Re-run the failed command to capture stderr
    local stderr_output
    stderr_output=$(eval "$last_cmd" 2>&1 >/dev/null)

    # Get the fix suggestion with stderr context
    local fix_cmd
    fix_cmd=$(tfllm fix-internal --command "$last_cmd" --exit-code "$exit_code" --stderr "$stderr_output" 2>/dev/null)

    if [ -z "$fix_cmd" ]; then
        echo "No fix suggested" >&2
        return 1
    fi

    echo "Suggested fix: $fix_cmd"

    # Check for execute flag
    if [ "$1" = "-e" ] || [ "$1" = "--execute" ]; then
        read -p "Execute? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            eval "$fix_cmd"
        fi
    fi
}}
'''
