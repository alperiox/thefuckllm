"""CLI interface for tfllm."""

import os
import re
import subprocess
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from .engine import get_engine
from .shells import get_shell
from . import client

app = typer.Typer(
    name="tfllm",
    help="CLI helper powered by local LLMs",
    no_args_is_help=True,
)
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


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
