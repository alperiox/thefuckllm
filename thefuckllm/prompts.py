"""Prompt templates for Qwen2.5-Coder using ChatML format."""

# ChatML tokens
IM_START = "<|im_start|>"
IM_END = "<|im_end|>"


def build_chatml_prompt(system: str, user: str) -> str:
    """Build a ChatML-formatted prompt."""
    return f"""{IM_START}system
{system}
{IM_END}
{IM_START}user
{user}
{IM_END}
{IM_START}assistant
"""


# System prompts
COMMAND_EXTRACTOR_SYSTEM = (
    "You're a simple tool name extractor. Given the user query, extract the "
    "required CLI tool's name. Respond with only the tool name, nothing else. "
    "For example, if the query is about 'uv cli', respond with just 'uv'."
)

CLI_EXPERT_SYSTEM = (
    "You are a CLI expert. Answer the user's question based strictly on the "
    "provided context. Give a short, concise explanation and the exact command example."
)

FIX_COMMAND_SYSTEM = """You fix typos and errors in shell commands. Given a failed command, output ONLY the corrected command.

Examples:
- "gti status" -> "git status" (typo: gti -> git)
- "dcoker ps" -> "docker ps" (typo: dcoker -> docker)
- "pytohn script.py" -> "python script.py" (typo: pytohn -> python)
- "ls -la /nonexistent" -> "ls -la ." (fix path if it doesn't exist)
- "git puhs" -> "git push" (typo: puhs -> push)

Rules:
1. Output ONLY the corrected command, nothing else
2. Fix typos in command names (gti->git, dcoker->docker)
3. Fix typos in subcommands and flags
4. Do NOT suggest installing tools or aliases
5. Do NOT output explanations, just the command"""


def command_extraction_prompt(query: str) -> str:
    """Prompt to extract command name from user query."""
    return build_chatml_prompt(
        COMMAND_EXTRACTOR_SYSTEM,
        f"Extract the CLI tool name from: {query}"
    )


def ask_prompt(query: str, context: list[str]) -> str:
    """Prompt for answering CLI questions."""
    context_text = "\n\n".join(context)
    return build_chatml_prompt(
        CLI_EXPERT_SYSTEM,
        f"Context:\n{context_text}\n\nQuestion: {query}"
    )


def fix_prompt(
    failed_command: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    context: list[str] | None = None,
) -> str:
    """Prompt for fixing failed commands."""
    user_msg = f"Fix this command: {failed_command}"

    if stderr:
        user_msg += f"\nError: {stderr[:500]}"

    return build_chatml_prompt(FIX_COMMAND_SYSTEM, user_msg)
