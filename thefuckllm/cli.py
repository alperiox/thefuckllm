"""CLI interface for tfllm."""

import os
import re
import subprocess
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .engine import get_engine
from .shells import get_shell
from . import client

app = typer.Typer(
    name="tfllm",
    help="CLI helper powered by local LLMs",
    no_args_is_help=True,
)
config_app = typer.Typer(help="Configuration management")
app.add_typer(config_app, name="config")

console = Console()


def read_terminal_log(num_lines: int = 30) -> str:
    """Read the last N lines from the script log file if available."""
    log_file = os.environ.get("SCRIPT_LOG_FILE", "")
    if not log_file or not os.path.exists(log_file):
        return ""

    try:
        with open(log_file, "r", errors="ignore") as f:
            lines = f.readlines()
            # Get last N lines, strip ANSI codes
            recent = lines[-num_lines:] if len(lines) > num_lines else lines
            # Join and clean up control characters
            content = "".join(recent)
            # Remove common ANSI escape sequences
            content = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', content)
            content = re.sub(r'\x1b\][^\x07]*\x07', '', content)  # OSC sequences
            content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)  # Control chars
            return content.strip()
    except Exception:
        return ""


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="Your CLI question")],
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show debug info")] = False,
):
    """Ask a CLI question and get an answer based on man pages.

    Example:
        tfllm ask "how to find files by name in linux"
    """
    # Try server first
    if client.is_server_running():
        with console.status("[bold green]Thinking..."):
            response = client.send_request("ask", query=question, verbose=verbose)

        if response.get("success"):
            console.print(Panel(response["result"], title="Answer", border_style="green"))
            return
        else:
            # Fall through to direct execution
            if verbose:
                console.print(f"[yellow]Server error: {response.get('error')}[/yellow]")

    # Direct execution (slower - loads model)
    engine = get_engine()

    with console.status("[bold green]Thinking..."):
        answer = engine.ask(question, verbose=verbose)

    console.print(Panel(answer, title="Answer", border_style="green"))


@app.command()
def fix(
    execute: Annotated[bool, typer.Option("--execute", "-e", help="Prompt to execute the fix")] = False,
):
    """Fix the last failed command.

    This command reads the last failed command from shell hooks.
    Run `tfllm init <shell>` first to set up shell integration.

    Example:
        tfllm fix        # Show the suggested fix
        tfllm fix -e     # Show and optionally execute the fix
    """
    # Read from environment (set by shell hooks)
    last_cmd = os.environ.get("__THEFUCKLLM_LAST_CMD", "")
    exit_code_str = os.environ.get("__THEFUCKLLM_EXIT_CODE", "1")

    if not last_cmd:
        console.print("[red]No previous command found.[/red]")
        console.print("Make sure you've set up shell integration with:")
        console.print("  eval \"$(tfllm init bash)\"  # or zsh/fish")
        raise typer.Exit(1)

    try:
        exit_code = int(exit_code_str)
    except ValueError:
        exit_code = 1

    # Read terminal output from script log file
    terminal_output = read_terminal_log(num_lines=30)

    # Try server first
    if client.is_server_running():
        with console.status("[bold green]Analyzing error..."):
            response = client.send_request(
                "fix",
                command=last_cmd,
                exit_code=exit_code,
                stderr=terminal_output,
            )

        if response.get("success"):
            fix_cmd = response["result"]
            if fix_cmd:
                console.print(f"[bold]Suggested fix:[/bold] {fix_cmd}")
                if execute and typer.confirm("Execute this command?"):
                    subprocess.run(fix_cmd, shell=True)
                return
            else:
                console.print("[yellow]No fix suggestion available.[/yellow]")
                raise typer.Exit(1)

    # Direct execution (slower - loads model)
    engine = get_engine()

    with console.status("[bold green]Analyzing error..."):
        fix_cmd = engine.fix(last_cmd, exit_code, stderr=terminal_output)

    if not fix_cmd:
        console.print("[yellow]No fix suggestion available.[/yellow]")
        raise typer.Exit(1)

    console.print(f"[bold]Suggested fix:[/bold] {fix_cmd}")

    if execute:
        if typer.confirm("Execute this command?"):
            subprocess.run(fix_cmd, shell=True)


@app.command("fix-internal", hidden=True)
def fix_internal(
    command: Annotated[str, typer.Option("--command", "-c", help="The failed command")],
    exit_code: Annotated[int, typer.Option("--exit-code", "-x", help="Exit code")] = 1,
    stdout: Annotated[str, typer.Option("--stdout", help="Command stdout")] = "",
    stderr: Annotated[str, typer.Option("--stderr", help="Command stderr")] = "",
):
    """Internal command for shell integration. Outputs only the fix command.

    This is called by the shell function, not by users directly.
    """
    # Read terminal output from script log file if available
    terminal_output = read_terminal_log(num_lines=30)

    # Use terminal output as context if no stderr provided
    if terminal_output and not stderr:
        stderr = terminal_output

    # Try server first
    if client.is_server_running():
        response = client.send_request(
            "fix",
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )
        if response.get("success") and response.get("result"):
            print(response["result"])
            return

    # Direct execution
    engine = get_engine()
    fix_cmd = engine.fix(command, exit_code, stdout, stderr)
    if fix_cmd:
        print(fix_cmd)


@app.command()
def init(
    shell: Annotated[str, typer.Argument(help="Shell type: bash, zsh, or fish")],
    alias: Annotated[str, typer.Option("--alias", "-a", help="Alias name for fix command")] = "fuck",
):
    """Output shell configuration for integration.

    Add this to your shell config file:

        # For bash (~/.bashrc):
        eval "$(tfllm init bash)"

        # For zsh (~/.zshrc):
        eval "$(tfllm init zsh)"

        # For fish (~/.config/fish/config.fish):
        tfllm init fish | source
    """
    try:
        shell_impl = get_shell(shell.lower())
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    print(shell_impl.get_init_script(alias))


@app.command()
def serve(
    foreground: Annotated[bool, typer.Option("--foreground", "-f", help="Run in foreground")] = False,
):
    """Start the background server to keep models loaded.

    This speeds up subsequent ask/fix commands significantly.

    Example:
        tfllm serve      # Start in background
        tfllm serve -f   # Start in foreground (for debugging)
    """
    if client.is_server_running():
        console.print("[yellow]Server is already running.[/yellow]")
        console.print(f"PID: {client.get_server_pid()}")
        raise typer.Exit(1)

    from .server import run_server

    if foreground:
        console.print("[bold]Starting server in foreground...[/bold]")
        console.print("Press Ctrl+C to stop.")
    else:
        console.print("[bold]Starting server in background...[/bold]")

    run_server(foreground=foreground)


@app.command()
def stop():
    """Stop the background server."""
    if not client.is_server_running():
        console.print("[yellow]Server is not running.[/yellow]")
        raise typer.Exit(1)

    pid = client.get_server_pid()
    if client.stop_server():
        console.print(f"[green]Server stopped (PID {pid}).[/green]")
    else:
        console.print("[red]Failed to stop server.[/red]")
        raise typer.Exit(1)


@app.command()
def status():
    """Check if the background server is running."""
    if client.is_server_running():
        pid = client.get_server_pid()
        console.print(f"[green]Server is running (PID {pid}).[/green]")

        # Try to ping
        response = client.send_request("ping")
        if response.get("success"):
            console.print("[green]Server is responsive.[/green]")
        else:
            console.print(f"[yellow]Server not responding: {response.get('error')}[/yellow]")
    else:
        console.print("[yellow]Server is not running.[/yellow]")
        console.print("Start it with: tfllm serve")


@app.command()
def download():
    """Download and cache the LLM models.

    This pre-downloads the models so first query is fast.
    """
    from .models import ensure_model

    console.print("[bold]Downloading models...[/bold]")

    with console.status("Downloading Q8_0 model (default)..."):
        path = ensure_model("q8_0")
        console.print(f"[green]Q8_0 ready:[/green] {path}")

    with console.status("Downloading Q4_K_M model (smaller)..."):
        path = ensure_model("q4_k_m")
        console.print(f"[green]Q4_K_M ready:[/green] {path}")

    console.print("[bold green]All models downloaded![/bold green]")


# ============================================================================
# Config Commands
# ============================================================================


@config_app.command("set-provider")
def config_set_provider(
    provider: Annotated[
        str, typer.Argument(help="Provider: local, openai, anthropic, gemini, openrouter")
    ],
):
    """Set the active LLM provider.

    Examples:
        tfllm config set-provider openai
        tfllm config set-provider local
    """
    from .config import ProviderType, get_config, reload_config

    try:
        provider_type = ProviderType(provider.lower())
    except ValueError:
        console.print(f"[red]Unknown provider: {provider}[/red]")
        console.print(f"Available providers: {[p.value for p in ProviderType]}")
        raise typer.Exit(1)

    # Check for API key if remote provider
    config = get_config()
    if provider_type != ProviderType.LOCAL:
        if not config.has_api_key(provider_type):
            from .config import API_KEY_ENV_VARS

            env_var = API_KEY_ENV_VARS.get(provider_type, "")
            console.print(
                f"[yellow]Warning: No API key found for {provider}.[/yellow]"
            )
            console.print(f"Set the {env_var} environment variable.")

    config.active_provider = provider_type
    config.save()
    reload_config()

    # Notify server if running
    if client.is_server_running():
        response = client.reload_provider()
        if response.get("success"):
            console.print("[dim]Server notified of provider change.[/dim]")

    console.print(f"[green]Active provider set to: {provider}[/green]")


@config_app.command("set-model")
def config_set_model(
    model: Annotated[
        str,
        typer.Argument(help="Model identifier or alias (e.g., sonnet, gpt-4o, haiku)"),
    ],
):
    """Set the active model for the current provider.

    You can use short aliases like 'sonnet', 'haiku', 'gpt4o', etc.
    Run 'tfllm config list-models' to see all available models and aliases.

    Examples:
        tfllm config set-model sonnet       # -> claude-3-5-sonnet-20241022
        tfllm config set-model gpt-4o
        tfllm config set-model haiku        # -> claude-3-5-haiku-20241022
        tfllm config set-model q4           # -> q4_k_m (for local provider)
    """
    from .config import get_config, reload_config, resolve_model_alias

    config = get_config()

    # Resolve alias to full model name
    resolved_model = resolve_model_alias(model)

    config.active_model = model  # Store original input
    config.save()
    reload_config()

    # Notify server if running
    if client.is_server_running():
        response = client.reload_provider()
        if response.get("success"):
            console.print("[dim]Server notified of model change.[/dim]")

    if resolved_model != model:
        console.print(f"[green]Active model set to: {model} -> {resolved_model}[/green]")
    else:
        console.print(f"[green]Active model set to: {model}[/green]")


@config_app.command("show")
def config_show():
    """Show current configuration."""
    from .config import API_KEY_ENV_VARS, ProviderType, get_config, resolve_model_alias

    config = get_config()

    console.print("[bold]Current Configuration:[/bold]")
    console.print(f"  Active provider: [cyan]{config.active_provider.value}[/cyan]")

    # Show both stored model and resolved model if different
    stored_model = config.active_model or "(default)"
    resolved_model = config.get_active_model()
    if config.active_model and resolve_model_alias(config.active_model) != config.active_model:
        console.print(f"  Active model: [cyan]{stored_model}[/cyan] -> [cyan]{resolved_model}[/cyan]")
    else:
        console.print(f"  Active model: [cyan]{resolved_model}[/cyan]")

    console.print(f"  Local quantization: [cyan]{config.local_quantization}[/cyan]")
    console.print(f"  Config file: [dim]{config.config_path()}[/dim]")

    console.print("\n[bold]API Keys:[/bold]")
    for provider in ProviderType:
        if provider == ProviderType.LOCAL:
            continue
        env_var = API_KEY_ENV_VARS.get(provider, "")
        has_key = config.has_api_key(provider)
        status = "[green]set[/green]" if has_key else "[red]not set[/red]"
        console.print(f"  {provider.value}: {status} ({env_var})")


@config_app.command("list-models")
def config_list_models():
    """List available models per provider (fetched dynamically from LiteLLM)."""
    from .config import DEFAULT_MODELS, MODEL_ALIASES, ProviderType, get_available_models

    # Models table
    table = Table(title="Available Models (from LiteLLM)")
    table.add_column("Provider", style="cyan")
    table.add_column("Model", style="white")
    table.add_column("Default", style="green")

    for provider in ProviderType:
        models = get_available_models(provider)
        default = DEFAULT_MODELS.get(provider, "")
        for i, model in enumerate(models):
            is_default = "yes" if model == default else ""
            # Only show provider name for first row
            provider_name = provider.value if i == 0 else ""
            table.add_row(provider_name, model, is_default)

    console.print(table)

    # Aliases table
    console.print("\n[bold]Model Aliases[/bold] (use these as shortcuts):")
    alias_table = Table(show_header=True)
    alias_table.add_column("Alias", style="yellow")
    alias_table.add_column("Resolves to", style="white")

    # Group aliases by target model for cleaner display
    alias_groups = {}
    for alias, target in MODEL_ALIASES.items():
        if target not in alias_groups:
            alias_groups[target] = []
        alias_groups[target].append(alias)

    for target, aliases in sorted(alias_groups.items()):
        alias_table.add_row(", ".join(sorted(aliases)), target)

    console.print(alias_table)

    console.print("\n[dim]Models fetched dynamically from LiteLLM. For OpenRouter, use any model from https://openrouter.ai/docs#models[/dim]")
    console.print("[dim]Example: tfllm config set-model sonnet[/dim]")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
