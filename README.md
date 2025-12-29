# thefuckllm

A CLI helper that fixes your command-line mistakes using local LLMs. Inspired by [thefuck](https://github.com/nvbn/thefuck), but powered by AI running entirely on your machine.

## Features

- **Fix failed commands** - Type `fuck` after a failed command to get a fix suggestion
- **Ask CLI questions** - Get answers about any command-line tool based on its man page
- **Multiple LLM providers** - Use local models or cloud APIs (OpenAI, Anthropic, Gemini, OpenRouter)
- **Runs locally by default** - No API keys required, complete privacy with local models
- **Smart context retrieval** - Uses semantic search over man pages with fallback to tldr and cheat.sh
- **Shell integration** - Works with bash, zsh, and fish
- **Background server** - Keep the model loaded for instant responses
- **Hot-swap providers** - Switch between models and providers at any time

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
| `tfllm config show` | Show current configuration |
| `tfllm config set-provider <provider>` | Switch LLM provider |
| `tfllm config set-model <model>` | Set the model to use |
| `tfllm config list-models` | List available models |

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

## Using Different Providers

By default, thefuckllm runs entirely locally using Qwen2.5-Coder-3B. You can also use cloud-based LLM providers for potentially better results.

### Supported Providers

| Provider | Environment Variable | Example Models |
|----------|---------------------|----------------|
| Local (default) | - | q4_k_m, q8_0 |
| OpenAI | `OPENAI_API_KEY` | gpt-4o, gpt-4o-mini, o1-mini |
| Anthropic | `ANTHROPIC_API_KEY` | claude-3-5-sonnet-20241022, claude-3-haiku-20240307 |
| Google Gemini | `GEMINI_API_KEY` | gemini-1.5-flash, gemini-1.5-pro |
| OpenRouter | `OPENROUTER_API_KEY` | Any model on openrouter.ai |

### Switching Providers

```bash
# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Switch to Anthropic
tfllm config set-provider anthropic

# Use a model (short aliases work!)
tfllm config set-model sonnet    # -> claude-3-5-sonnet-20241022
tfllm config set-model haiku     # -> claude-3-5-haiku-20241022
tfllm config set-model opus      # -> claude-3-opus-20240229

# Check current configuration
tfllm config show

# Switch back to local
tfllm config set-provider local
```

### Model Aliases

You can use short aliases instead of full model names:

| Alias | Resolves to |
|-------|-------------|
| `sonnet` | claude-3-5-sonnet-20241022 |
| `haiku` | claude-3-5-haiku-20241022 |
| `opus` | claude-3-opus-20240229 |
| `gpt4o`, `4o` | gpt-4o |
| `4o-mini` | gpt-4o-mini |
| `gemini`, `flash` | gemini/gemini-1.5-flash |
| `gemini-pro` | gemini/gemini-1.5-pro |
| `q4`, `q8` | q4_k_m, q8_0 (local) |

Run `tfllm config list-models` to see all available models and aliases.

### Using OpenRouter

OpenRouter provides access to many models from various providers through a single API:

```bash
export OPENROUTER_API_KEY="sk-or-..."
tfllm config set-provider openrouter
tfllm config set-model openrouter/openai/gpt-4o-mini
```

See available models at [openrouter.ai/docs#models](https://openrouter.ai/docs#models).

### Configuration

Configuration is stored in `~/.config/thefuckllm/config.toml` (or platform equivalent). API keys are read from environment variables for security.

```bash
# View all available models
tfllm config list-models

# Show current settings
tfllm config show
```

When you change the provider or model, the background server (if running) is automatically notified to reload.

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
- `litellm` - Unified API for multiple LLM providers
- `fastembed` - Text embeddings for semantic retrieval
- `huggingface-hub` - Model downloading
- `typer` - CLI framework
- `rich` - Terminal formatting

## License

MIT
