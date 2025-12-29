"""Client for communicating with tfllm background server."""

import json
import os
import signal
import socket
from pathlib import Path

from .server import get_socket_path, get_pid_file


def is_server_running() -> bool:
    """Check if the server is running."""
    socket_path = get_socket_path()
    pid_file = get_pid_file()

    if not socket_path.exists():
        return False

    if not pid_file.exists():
        return False

    # Check if PID is still alive
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)  # Signal 0 just checks if process exists
        return True
    except (ProcessLookupError, ValueError):
        # Process not found or invalid PID
        return False
    except PermissionError:
        # Process exists but we can't signal it
        return True


def send_request(action: str, **kwargs) -> dict:
    """Send a request to the server.

    Args:
        action: The action to perform ("ask", "fix", "ping")
        **kwargs: Additional arguments for the action

    Returns:
        Response dict with "success" and "result" or "error"

    Raises:
        ConnectionError: If unable to connect to server
    """
    socket_path = get_socket_path()

    if not socket_path.exists():
        raise ConnectionError("Server socket not found. Is the server running?")

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(str(socket_path))
        sock.settimeout(60.0)  # 60 second timeout for LLM inference

        # Send request
        request = {"action": action, **kwargs}
        sock.sendall(json.dumps(request).encode("utf-8"))
        sock.shutdown(socket.SHUT_WR)  # Signal end of request

        # Receive response
        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk

        if not data:
            return {"success": False, "error": "Empty response from server"}

        return json.loads(data.decode("utf-8"))

    except socket.timeout:
        return {"success": False, "error": "Request timed out"}
    except ConnectionRefusedError:
        return {"success": False, "error": "Connection refused. Server may have crashed."}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        sock.close()


def stop_server() -> bool:
    """Stop the running server.

    Returns:
        True if server was stopped, False otherwise
    """
    pid_file = get_pid_file()
    socket_path = get_socket_path()

    if not pid_file.exists():
        return False

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)

        # Clean up files
        if pid_file.exists():
            pid_file.unlink()
        if socket_path.exists():
            socket_path.unlink()

        return True
    except (ProcessLookupError, ValueError):
        # Process already dead, clean up files
        if pid_file.exists():
            pid_file.unlink()
        if socket_path.exists():
            socket_path.unlink()
        return False
    except PermissionError:
        return False


def get_server_pid() -> int | None:
    """Get the PID of the running server."""
    pid_file = get_pid_file()

    if not pid_file.exists():
        return None

    try:
        return int(pid_file.read_text().strip())
    except ValueError:
        return None


def reload_provider() -> dict:
    """Signal server to reload the LLM provider.

    Call this after changing the config (provider, model, etc.)
    to make the server use the new settings.

    Returns:
        Response dict with "success" and "result" or "error"
    """
    if not is_server_running():
        return {"success": False, "error": "Server not running"}
    return send_request("reload_provider")
