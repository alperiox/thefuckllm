"""Fish shell integration."""

from .base import Shell


class Fish(Shell):
    """Fish shell hook implementation."""

    @property
    def name(self) -> str:
        return "fish"

    def get_init_script(self, alias: str = "fuck") -> str:
        """Generate fish initialization script.

        Uses fish events and the $history variable.
        Re-runs failed command to capture stderr for the LLM.
        """
        return f'''
# thefuckllm shell integration for fish

function __thefuckllm_postexec --on-event fish_postexec
    set -gx __THEFUCKLLM_LAST_CMD $argv[1]
    set -gx __THEFUCKLLM_EXIT_CODE $status
end

function {alias}
    set -l last_cmd $__THEFUCKLLM_LAST_CMD
    set -l exit_code $__THEFUCKLLM_EXIT_CODE

    if test -z "$last_cmd"
        set last_cmd $history[1]
    end

    if test -z "$last_cmd"
        echo "No previous command found" >&2
        return 1
    end

    # Re-run the failed command to capture stderr
    set -l stderr_output (eval $last_cmd 2>&1 >/dev/null)

    # Get the fix suggestion with stderr context
    set -l fix_cmd (tfllm fix-internal --command "$last_cmd" --exit-code "$exit_code" --stderr "$stderr_output" 2>/dev/null)

    if test -z "$fix_cmd"
        echo "No fix suggested" >&2
        return 1
    end

    echo "Suggested fix: $fix_cmd"

    # Check for execute flag
    if contains -- -e $argv; or contains -- --execute $argv
        read -l -P "Execute? [y/N] " confirm
        if string match -qir '^y' -- $confirm
            eval $fix_cmd
        end
    end
end
'''
