"""Background server for tfllm - keeps model loaded for fast inference."""

import json
import os
import signal
import socket
import sys
from pathlib import Path

# Disable tokenizers parallelism to avoid fork warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from platformdirs import user_cache_dir

from .engine import InferenceEngine
from .models import get_llm

# Server configuration
CACHE_DIR = Path(user_cache_dir("thefuckllm"))
SOCKET_PATH = CACHE_DIR / "tfllm.sock"
PID_FILE = CACHE_DIR / "tfllm.pid"


def get_socket_path() -> Path:
    """Get the Unix socket path."""
    return SOCKET_PATH


def get_pid_file() -> Path:
    """Get the PID file path."""
    return PID_FILE


class Server:
    """Background server that keeps model loaded."""

    def __init__(self):
        self.engine: InferenceEngine | None = None
        self.running = False
        self.socket: socket.socket | None = None

    def preload_models(self):
        """Preload all models for fast inference."""
        print("Loading LLM model...")
        get_llm()  # This caches the model

        print("Loading embedding model...")
        self.engine = InferenceEngine()
        # Trigger lazy loading of embedding model
        _ = self.engine.retriever.emb

        print("Models loaded and ready!")

    def handle_request(self, data: dict) -> dict:
        """Handle a single request from client."""
        action = data.get("action")

        if self.engine is None:
            return {"success": False, "error": "Engine not initialized"}

        try:
            if action == "ask":
                query = data.get("query", "")
                verbose = data.get("verbose", False)
                result = self.engine.ask(query, verbose=verbose)
                return {"success": True, "result": result}

            elif action == "fix":
                command = data.get("command", "")
                exit_code = data.get("exit_code", 1)
                stdout = data.get("stdout", "")
                stderr = data.get("stderr", "")
                verbose = data.get("verbose", False)
                result = self.engine.fix(command, exit_code, stdout, stderr, verbose)
                return {"success": True, "result": result}

            elif action == "ping":
                return {"success": True, "result": "pong"}

            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def handle_client(self, conn: socket.socket):
        """Handle a client connection."""
        try:
            # Receive data (max 64KB should be enough)
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                # Check for end of JSON
                try:
                    request = json.loads(data.decode("utf-8"))
                    break
                except json.JSONDecodeError:
                    continue

            if data:
                request = json.loads(data.decode("utf-8"))
                response = self.handle_request(request)
                conn.sendall(json.dumps(response).encode("utf-8"))

        except Exception as e:
            error_response = {"success": False, "error": str(e)}
            try:
                conn.sendall(json.dumps(error_response).encode("utf-8"))
            except Exception:
                pass
        finally:
            conn.close()

    def cleanup(self):
        """Clean up socket and PID file."""
        if self.socket:
            self.socket.close()
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
        if PID_FILE.exists():
            PID_FILE.unlink()

    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print("\nShutting down server...")
        self.running = False
        self.cleanup()
        sys.exit(0)

    def run(self, foreground: bool = False):
        """Run the server."""
        # Ensure cache directory exists
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Check if already running
        if SOCKET_PATH.exists():
            print(f"Socket already exists at {SOCKET_PATH}")
            print("Server may already be running. Use 'tfllm stop' first.")
            sys.exit(1)

        # Daemonize if not foreground
        if not foreground:
            pid = os.fork()
            if pid > 0:
                # Parent process - write PID and exit
                PID_FILE.write_text(str(pid))
                print(f"Server started with PID {pid}")
                sys.exit(0)

            # Child process - become daemon
            os.setsid()
            os.chdir("/")

            # Redirect standard file descriptors
            sys.stdin = open(os.devnull, "r")
            sys.stdout = open(CACHE_DIR / "server.log", "a")
            sys.stderr = sys.stdout

        # Write PID file (for foreground mode or child process)
        if foreground:
            PID_FILE.write_text(str(os.getpid()))

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

        # Preload models
        self.preload_models()

        # Create Unix socket
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(SOCKET_PATH))
        self.socket.listen(5)
        self.socket.settimeout(1.0)  # Allow periodic check for shutdown

        print(f"Server listening on {SOCKET_PATH}")
        self.running = True

        while self.running:
            try:
                conn, _ = self.socket.accept()
                self.handle_client(conn)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {e}")

        self.cleanup()


def run_server(foreground: bool = False):
    """Entry point to run the server."""
    server = Server()
    server.run(foreground=foreground)
