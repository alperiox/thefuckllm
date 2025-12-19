"""Rule-based typo correction using edit distance."""

import os
import subprocess
from functools import lru_cache


@lru_cache(maxsize=1)
def get_available_commands() -> set[str]:
    """Get all available commands from PATH."""
    commands = set()

    # Get commands from PATH
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for directory in path_dirs:
        if os.path.isdir(directory):
            try:
                for item in os.listdir(directory):
                    item_path = os.path.join(directory, item)
                    if os.access(item_path, os.X_OK):
                        commands.add(item)
            except PermissionError:
                continue

    # Add common commands that might be aliases/builtins
    common = {
        "git", "docker", "python", "python3", "pip", "npm", "node",
        "cargo", "go", "ruby", "java", "mvn", "gradle",
        "ls", "cd", "cat", "grep", "find", "sed", "awk",
        "curl", "wget", "ssh", "scp", "rsync",
        "vim", "nano", "code", "subl",
        "make", "cmake", "gcc", "clang",
        "kubectl", "helm", "terraform", "aws", "gcloud", "az",
        "brew", "apt", "yum", "pacman", "dnf",
        "systemctl", "journalctl", "service",
        "uv", "poetry", "pipenv", "conda",
    }
    commands.update(common)

    return commands


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def find_closest_command(typo: str, max_distance: int = 2) -> str | None:
    """Find the closest matching command for a typo."""
    commands = get_available_commands()

    # Exact match
    if typo in commands:
        return None  # Not a typo

    # Find closest match
    best_match = None
    best_distance = max_distance + 1

    for cmd in commands:
        # Skip if length difference is too big
        if abs(len(cmd) - len(typo)) > max_distance:
            continue

        distance = levenshtein_distance(typo.lower(), cmd.lower())
        if distance < best_distance:
            best_distance = distance
            best_match = cmd

    if best_distance <= max_distance:
        return best_match

    return None


def fix_command_typo(failed_command: str) -> str | None:
    """
    Try to fix a command typo using edit distance.

    Returns the corrected command or None if no fix found.
    """
    parts = failed_command.strip().split()
    if not parts:
        return None

    cmd = parts[0]
    args = parts[1:]

    # Try to find a close match for the command
    fixed_cmd = find_closest_command(cmd)

    if fixed_cmd:
        # Return the fixed command with original args
        if args:
            return f"{fixed_cmd} {' '.join(args)}"
        return fixed_cmd

    # If the command exists, maybe the subcommand is wrong
    if cmd in get_available_commands() and args:
        # Try to fix common subcommand typos for known tools
        subcommand_fixes = try_fix_subcommand(cmd, args)
        if subcommand_fixes:
            return subcommand_fixes

    return None


def try_fix_subcommand(cmd: str, args: list[str]) -> str | None:
    """Try to fix subcommand typos for known tools."""
    if not args:
        return None

    subcommand = args[0]
    rest = args[1:]

    # Known subcommands for common tools
    known_subcommands: dict[str, list[str]] = {
        "git": [
            "status", "add", "commit", "push", "pull", "fetch", "merge",
            "checkout", "branch", "log", "diff", "stash", "rebase", "reset",
            "clone", "init", "remote", "tag", "cherry-pick", "revert",
        ],
        "docker": [
            "run", "ps", "images", "build", "pull", "push", "exec",
            "stop", "start", "restart", "rm", "rmi", "logs", "inspect",
            "compose", "network", "volume", "system", "container", "image",
        ],
        "kubectl": [
            "get", "describe", "apply", "delete", "create", "edit",
            "logs", "exec", "port-forward", "scale", "rollout",
        ],
        "npm": [
            "install", "run", "start", "test", "build", "publish",
            "init", "update", "uninstall", "list", "audit", "ci",
        ],
        "pip": [
            "install", "uninstall", "list", "show", "freeze", "search",
            "download", "wheel", "check", "config", "cache",
        ],
        "uv": [
            "sync", "run", "add", "remove", "lock", "pip", "venv",
            "init", "build", "publish", "tool", "python",
        ],
    }

    if cmd not in known_subcommands:
        return None

    # Find closest subcommand
    best_match = None
    best_distance = 3  # Max distance for subcommands

    for known_sub in known_subcommands[cmd]:
        distance = levenshtein_distance(subcommand.lower(), known_sub.lower())
        if distance < best_distance:
            best_distance = distance
            best_match = known_sub

    if best_match and best_distance <= 2:
        if rest:
            return f"{cmd} {best_match} {' '.join(rest)}"
        return f"{cmd} {best_match}"

    return None
