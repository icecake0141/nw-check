# Copyright 2025 nw-check contributors
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# This file was created or modified with the assistance of an AI (Large Language Model).
# Review required for correctness, security, and licensing.
"""Supervisor and control server for nw-check execution."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Sequence

_LOGGER = logging.getLogger(__name__)


class ProcessSupervisor:
    """Manage the lifecycle of a nw-check process and its process group."""

    def __init__(self, command: Sequence[str], terminate_timeout: float = 5.0) -> None:
        self._command = list(command)
        self._terminate_timeout = terminate_timeout
        self._process: subprocess.Popen[str] | None = None
        self._paused = False
        self._lock = threading.Lock()
        self._pgid: int | None = None

    def start(self) -> subprocess.Popen[str]:
        """Start the managed process."""

        with self._lock:
            if self._process is not None:
                raise RuntimeError("process already started")
            preexec_fn = os.setsid if os.name == "posix" else None
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            self._process = subprocess.Popen(
                self._command,
                text=True,
                preexec_fn=preexec_fn,
                creationflags=creationflags,
            )
            if os.name == "posix":
                self._pgid = os.getpgid(self._process.pid)
            else:
                self._pgid = None
            _LOGGER.info("Started nw-check process pid=%s", self._process.pid)
            return self._process

    def pause(self) -> tuple[bool, str]:
        """Pause the managed process group."""

        with self._lock:
            if not self._is_running_locked():
                return False, "not_running"
            if self._paused:
                return False, "already_paused"
            if os.name != "posix":
                return False, "unsupported"
            if self._pgid is None:
                return False, "process_group_missing"
            os.killpg(self._pgid, signal.SIGSTOP)
            self._paused = True
            return True, "paused"

    def resume(self) -> tuple[bool, str]:
        """Resume the managed process group."""

        with self._lock:
            if not self._is_running_locked():
                return False, "not_running"
            if not self._paused:
                return False, "not_paused"
            if os.name != "posix":
                return False, "unsupported"
            if self._pgid is None:
                return False, "process_group_missing"
            os.killpg(self._pgid, signal.SIGCONT)
            self._paused = False
            return True, "resumed"

    def terminate(self) -> tuple[bool, str]:
        """Terminate the process group and wait for exit."""

        with self._lock:
            if not self._process:
                return False, "not_started"
            if self._process.poll() is not None:
                return False, "already_exited"
            if os.name == "posix" and self._pgid is not None:
                os.killpg(self._pgid, signal.SIGTERM)
            else:
                self._process.terminate()
        try:
            self._process.wait(timeout=self._terminate_timeout)
        except subprocess.TimeoutExpired:
            _LOGGER.warning("Process did not terminate in time; force killing")
            with self._lock:
                if os.name == "posix" and self._pgid is not None:
                    os.killpg(self._pgid, signal.SIGKILL)
                else:
                    self._process.kill()
            self._process.wait(timeout=self._terminate_timeout)
        with self._lock:
            self._paused = False
        return True, "terminated"

    def status(self) -> dict[str, Any]:
        """Return status information for the managed process."""

        with self._lock:
            process = self._process
            pid = process.pid if process else None
            return_code = process.poll() if process else None
            if return_code is not None:
                state = "exited"
                self._paused = False
            elif self._paused:
                state = "paused"
            elif process is None:
                state = "not_started"
            else:
                state = "running"
            return {
                "command": self._command,
                "pid": pid,
                "pgid": self._pgid,
                "status": state,
                "return_code": return_code,
            }

    def wait(self) -> int | None:
        """Wait for the managed process to exit."""

        process = self._process
        if not process:
            return None
        return process.wait()

    def _is_running_locked(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None


class ControlHTTPServer(HTTPServer):
    """HTTP server carrying supervisor context."""

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler: type[BaseHTTPRequestHandler],
        supervisor: ProcessSupervisor,
        token: str | None,
        stop_event: threading.Event,
    ) -> None:
        super().__init__(server_address, request_handler)
        self.supervisor = supervisor
        self.token = token
        self.stop_event = stop_event


class ControlRequestHandler(BaseHTTPRequestHandler):
    """Handle control requests for the nw-check supervisor."""

    server: ControlHTTPServer

    def do_GET(self) -> None:  # pylint: disable=invalid-name
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if not self._is_authorized(parsed):
            self._send_text(401, "Unauthorized")
            return
        if path == "/":
            self._send_html(self._render_page())
            return
        if path == "/api/status":
            self._send_json(200, self.server.supervisor.status())
            return
        self._send_text(404, "Not Found")

    def do_POST(self) -> None:  # pylint: disable=invalid-name
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if not self._is_authorized(parsed):
            self._send_text(401, "Unauthorized")
            return
        if path == "/api/pause":
            ok, message = self.server.supervisor.pause()
            self._send_json(200 if ok else 409, {"ok": ok, "message": message})
            return
        if path == "/api/resume":
            ok, message = self.server.supervisor.resume()
            self._send_json(200 if ok else 409, {"ok": ok, "message": message})
            return
        if path == "/api/terminate":
            ok, message = self.server.supervisor.terminate()
            self._send_json(200 if ok else 409, {"ok": ok, "message": message})
            return
        if path == "/api/shutdown":
            self._send_json(200, {"ok": True, "message": "shutdown_requested"})
            self.server.stop_event.set()
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        self._send_text(404, "Not Found")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        _LOGGER.info("Control server: %s", format % args)

    def _is_authorized(self, parsed: urllib.parse.ParseResult) -> bool:
        token = self.server.token
        if not token:
            return True
        header_token = self.headers.get("X-Control-Token")
        if header_token == token:
            return True
        query = urllib.parse.parse_qs(parsed.query)
        return query.get("token", [None])[0] == token

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_text(self, status: int, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _render_page(self) -> str:
        token = self.server.token or ""
        token_line = f"const token = '{token}';" if token else "const token = '';"
        return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>nw-check Control</title>
    <style>
      body {{ font-family: sans-serif; margin: 2rem; }}
      button {{ margin-right: 0.5rem; padding: 0.4rem 0.8rem; }}
      .status {{ margin-top: 1rem; padding: 0.6rem; background: #f4f4f4; }}
    </style>
  </head>
  <body>
    <h1>nw-check Control</h1>
    <div>
      <button onclick=\"pauseRun()\">Pause</button>
      <button onclick=\"resumeRun()\">Resume</button>
      <button onclick=\"terminateRun()\">Terminate</button>
      <button onclick=\"shutdownServer()\">Shutdown Server</button>
    </div>
    <div class=\"status\" id=\"status\">Loading...</div>
    <script>
      {token_line}
      const headers = token ? {{ 'X-Control-Token': token }} : {{}};
      async function call(path) {{
        const response = await fetch(path, {{ method: 'POST', headers }});
        return response.json();
      }}
      async function refresh() {{
        const response = await fetch('/api/status', {{ headers }});
        const data = await response.json();
        document.getElementById('status').textContent = JSON.stringify(data, null, 2);
      }}
      async function pauseRun() {{ await call('/api/pause'); await refresh(); }}
      async function resumeRun() {{ await call('/api/resume'); await refresh(); }}
      async function terminateRun() {{ await call('/api/terminate'); await refresh(); }}
      async function shutdownServer() {{ await call('/api/shutdown'); }}
      refresh();
      setInterval(refresh, 2000);
    </script>
  </body>
</html>
"""


def build_nw_check_command(args: argparse.Namespace) -> list[str]:
    """Build the nw-check command to run under supervision."""

    command = [
        sys.executable,
        "-m",
        "nw_check.cli",
        "--devices",
        args.devices,
        "--tobe",
        args.tobe,
        "--out-dir",
        args.out_dir,
        "--snmp-timeout",
        str(args.snmp_timeout),
        "--snmp-retries",
        str(args.snmp_retries),
        "--log-level",
        args.log_level,
    ]
    if args.snmp_verbose:
        command.append("--snmp-verbose")
    return command


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for the supervisor."""

    parser = argparse.ArgumentParser(description="nw-check supervisor")
    parser.add_argument("--devices", required=True, help="path to device inventory CSV")
    parser.add_argument("--tobe", required=True, help="path to To-Be wiring CSV")
    parser.add_argument("--out-dir", required=True, help="output directory")
    parser.add_argument("--snmp-timeout", type=int, default=2, help="SNMP timeout seconds")
    parser.add_argument("--snmp-retries", type=int, default=1, help="SNMP retries")
    parser.add_argument(
        "--snmp-verbose",
        action="store_true",
        help="enable verbose SNMP command logging (redacted secrets)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["INFO", "DEBUG", "WARN"],
        help="log level",
    )
    parser.add_argument("--control-host", default="127.0.0.1", help="control host")
    parser.add_argument("--control-port", type=int, default=8080, help="control port")
    parser.add_argument(
        "--control-token",
        default=None,
        help="optional token required for control requests",
    )
    parser.add_argument(
        "--shutdown-on-exit",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="shutdown the control server when nw-check exits",
    )
    parser.add_argument(
        "--terminate-timeout",
        type=float,
        default=5.0,
        help="seconds to wait before force killing",
    )
    return parser


def configure_logging(level: str) -> None:
    """Configure logging."""

    logging.basicConfig(level=getattr(logging, level), format="%(levelname)s %(message)s")


def main() -> int:
    """Run the supervisor and control server."""

    parser = build_parser()
    args = parser.parse_args()
    configure_logging(args.log_level)

    command = build_nw_check_command(args)
    supervisor = ProcessSupervisor(command, terminate_timeout=args.terminate_timeout)
    supervisor.start()

    stop_event = threading.Event()
    server = ControlHTTPServer(
        (args.control_host, args.control_port),
        ControlRequestHandler,
        supervisor,
        args.control_token,
        stop_event,
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    _LOGGER.info("Control server listening on %s:%s", args.control_host, args.control_port)

    exit_code = supervisor.wait()
    if args.shutdown_on_exit:
        _LOGGER.info("nw-check exited; shutting down control server")
        stop_event.set()
        server.shutdown()
        server_thread.join(timeout=2)
    else:
        _LOGGER.info("nw-check exited; control server remains active")
    while not stop_event.is_set():
        time.sleep(0.5)
    return exit_code or 0


if __name__ == "__main__":
    raise SystemExit(main())
