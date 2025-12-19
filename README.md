# thefuckllm

A CLI helper that fixes your command-line mistakes using local LLMs. Inspired by [thefuck](https://github.com/nvbn/thefuck), but powered by AI running entirely on your machine.

## Features

- **Fix failed commands** - Type `fuck` after a failed command to get a fix suggestion
- **Ask CLI questions** - Get answers about any command-line tool based on its man page
- **Runs locally** - No API keys, no cloud services, complete privacy
- **Smart context retrieval** - Uses semantic search over man pages with fallback to tldr and cheat.sh
- **Shell integration** - Works with bash, zsh, and fish
- **Background server** - Keep the model loaded for instant responses

## Installation

Requires Python 3.12+ and [uv](https://github.com/astral-sh/uv).

```bash
# Clone the repository
git clone https://github.com/yourusername/thefuckllm.git
cd thefuckllm

# Install dependencies
uv sync

# Download the LLM models (optional - happens automatically on first use)
uv run tfllm download
```

## Quick Start

### Shell Integration

Add this to your shell config to enable the `fuck` command:

```bash
# Bash (~/.bashrc)
eval "$(tfllm init bash)"

# Zsh (~/.zshrc)
eval "$(tfllm init zsh)"

# Fish (~/.config/fish/config.fish)
tfllm init fish | source
```

Then restart your shell or source the config file.

### Usage

**Fix a failed command:**
```bash
$ gti status
bash: gti: command not found

$ fuck
Suggested fix: git status
Execute? [y/N] y
# Runs: git status
```

**Ask a question:**
```bash
$ tfllm ask "how to find files by name recursively"
```

**Run with execute flag:**
```bash
$ fuck -e  # Automatically prompts to execute the fix
```

## Commands

| Command | Description |
|---------|-------------|
| `tfllm ask "question"` | Ask a CLI question |
| `tfllm fix` | Show fix for the last failed command |
| `tfllm fix -e` | Show fix and prompt to execute |
| `tfllm init <shell>` | Output shell integration script |
| `tfllm serve` | Start background server (faster responses) |
| `tfllm stop` | Stop the background server |
| `tfllm status` | Check if server is running |
| `tfllm download` | Pre-download the LLM models |

## Background Server

For faster responses, run the background server to keep models loaded in memory:

```bash
# Start in background
tfllm serve

# Check status
tfllm status

# Stop when done
tfllm stop
```

Without the server, each command loads the model fresh (slower first response). With the server running, responses are near-instant.

## How It Works

1. **Command Extraction** - The LLM identifies which CLI tool you're asking about
2. **Context Retrieval** - Fetches the man page and uses semantic search (BGE-small embeddings) to find relevant sections
3. **Fallback Sources** - If no man page exists, falls back to tldr and cheat.sh
4. **Answer Generation** - The LLM generates a concise answer with the exact command

For command fixing:
1. Shell hooks capture the failed command and exit code
2. The error output is analyzed along with man page context
3. A corrected command is suggested

## Models

Uses [Qwen2.5-Coder-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF) via llama.cpp:

- **Q8_0** (default) - Higher quality, ~3.5GB
- **Q4_K_M** - Smaller size, ~2GB

Models are cached in `~/.cache/thefuckllm/` (or platform equivalent).

## Requirements

- Python 3.12+
- A GPU with Metal (macOS) or CUDA support is recommended for fast inference
- ~4GB disk space for models
- `tldr` CLI (optional, for fallback context)

## Dependencies

- `llama-cpp-python` - Local GGUF model inference
- `fastembed` - Text embeddings for semantic retrieval
- `huggingface-hub` - Model downloading
- `typer` - CLI framework
- `rich` - Terminal formatting

## License

MIT
