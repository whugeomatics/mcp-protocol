#!/usr/bin/env python3
"""
MCP Logger - A transparent proxy between MCP Host and MCP Server.

Usage in MCP config:
    python mcp_logger.py <real_server_command> [args...]

Example:
    python mcp_logger.py uv run weather.py

This script sits between the MCP host and the real MCP server,
forwarding all stdin/stdout traffic while logging everything to a file.
"""

import sys
import os
import subprocess
import threading
import datetime

# Log file path - same directory as this script
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "mcp_traffic.log")


def get_timestamp():
    """Get current timestamp string."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def log_message(direction, data):
    """
    Log a message to the log file.

    Args:
        direction: 'HOST -> SERVER' or 'SERVER -> HOST'
        data: The raw data being transmitted
    """
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = get_timestamp()
            f.write(f"\n{'='*80}\n")
            f.write(f"[{timestamp}] {direction}\n")
            f.write(f"{'-'*80}\n")
            if isinstance(data, bytes):
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    text = repr(data)
            else:
                text = data
            f.write(text)
            if not text.endswith("\n"):
                f.write("\n")
            f.flush()
    except Exception as e:
        # Write errors to stderr so they don't interfere with MCP protocol
        print(f"[mcp_logger] Error writing log: {e}", file=sys.stderr)


def forward_host_to_server(host_stdin, server_stdin):
    """
    Read from host's stdin and forward to server's stdin.
    Logs all traffic as HOST -> SERVER.
    """
    try:
        while True:
            # Read one line at a time (MCP JSON-RPC messages are line-delimited)
            line = host_stdin.readline()
            if not line:
                # Host closed stdin, close server's stdin too
                log_message("HOST -> SERVER", "[EOF - Host closed connection]")
                server_stdin.close()
                break

            log_message(
                "HOST -> SERVER",
                line.decode("utf-8") if isinstance(line, bytes) else line,
            )

            try:
                server_stdin.write(line)
                server_stdin.flush()
            except (BrokenPipeError, OSError):
                log_message("HOST -> SERVER", "[ERROR - Server pipe broken]")
                break
    except Exception as e:
        log_message("HOST -> SERVER", f"[ERROR] {e}")


def forward_server_to_host(server_stdout, host_stdout):
    """
    Read from server's stdout and forward to host's stdout.
    Logs all traffic as SERVER -> HOST.
    """
    try:
        while True:
            line = server_stdout.readline()
            if not line:
                # Server closed stdout
                log_message("SERVER -> HOST", "[EOF - Server closed connection]")
                break

            log_message(
                "SERVER -> HOST",
                line.decode("utf-8") if isinstance(line, bytes) else line,
            )

            try:
                host_stdout.write(line)
                host_stdout.flush()
            except (BrokenPipeError, OSError):
                log_message("SERVER -> HOST", "[ERROR - Host pipe broken]")
                break
    except Exception as e:
        log_message("SERVER -> HOST", f"[ERROR] {e}")


def forward_server_stderr(server_stderr):
    """
    Read from server's stderr and log it, also forward to our stderr.
    """
    try:
        while True:
            line = server_stderr.readline()
            if not line:
                break

            text = line.decode("utf-8") if isinstance(line, bytes) else line
            log_message("SERVER STDERR", text)

            # Also forward to our stderr
            sys.stderr.write(text)
            sys.stderr.flush()
    except Exception as e:
        log_message("SERVER STDERR", f"[ERROR] {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python mcp_logger.py <command> [args...]", file=sys.stderr)
        print("Example: python mcp_logger.py uv run weather.py", file=sys.stderr)
        sys.exit(1)

    # The real server command is everything after mcp_logger.py
    server_command = sys.argv[1:]

    # Initialize log file
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{'#'*80}\n")
        f.write(f"# MCP Logger Session Started: {get_timestamp()}\n")
        f.write(f"# Server Command: {' '.join(server_command)}\n")
        f.write(f"{'#'*80}\n")

    # Start the real MCP server as a subprocess
    try:
        process = subprocess.Popen(
            server_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,  # Unbuffered for real-time forwarding
        )
    except FileNotFoundError:
        print(
            f"[mcp_logger] Error: Command not found: {server_command[0]}",
            file=sys.stderr,
        )
        log_message("SYSTEM", f"Error: Command not found: {server_command[0]}")
        sys.exit(1)
    except Exception as e:
        print(f"[mcp_logger] Error starting server: {e}", file=sys.stderr)
        log_message("SYSTEM", f"Error starting server: {e}")
        sys.exit(1)

    log_message("SYSTEM", f"Server process started (PID: {process.pid})")

    # Use binary mode for stdin/stdout to avoid encoding issues
    host_stdin = sys.stdin.buffer
    host_stdout = sys.stdout.buffer

    # Create forwarding threads
    # Thread 1: Host stdin -> Server stdin
    t_host_to_server = threading.Thread(
        target=forward_host_to_server,
        args=(host_stdin, process.stdin),
        daemon=True,
        name="host-to-server",
    )

    # Thread 2: Server stdout -> Host stdout
    t_server_to_host = threading.Thread(
        target=forward_server_to_host,
        args=(process.stdout, host_stdout),
        daemon=True,
        name="server-to-host",
    )

    # Thread 3: Server stderr -> Log + our stderr
    t_server_stderr = threading.Thread(
        target=forward_server_stderr,
        args=(process.stderr,),
        daemon=True,
        name="server-stderr",
    )

    # Start all forwarding threads
    t_host_to_server.start()
    t_server_to_host.start()
    t_server_stderr.start()

    # Wait for the server process to exit
    try:
        return_code = process.wait()
        log_message("SYSTEM", f"Server process exited with code: {return_code}")
    except KeyboardInterrupt:
        log_message("SYSTEM", "Received KeyboardInterrupt, terminating server...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log_message("SYSTEM", "Server process terminated.")

    # Give threads a moment to finish flushing
    t_server_to_host.join(timeout=2)
    t_host_to_server.join(timeout=2)
    t_server_stderr.join(timeout=2)

    log_message("SYSTEM", "MCP Logger session ended.")

    sys.exit(return_code if "return_code" in dir() else 0)


if __name__ == "__main__":
    main()
