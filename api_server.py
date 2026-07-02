"""
Simple HTTP API server for bot log inspection.
Run: python api_server.py [--port 8502]

Endpoints:
  GET /log?order_id=ORD-xxx       — search all log files for lines containing order_id
  GET /log?session_id=xxx         — return last N lines of session's log file
  GET /log?file=logs/bot_xxx.log  — return last N lines of a specific log file
  GET /sessions                   — list all sessions from bot_history.json
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

LOG_DIR = "logs"
HISTORY_FILE = "data/bot_history.json"
DEFAULT_TAIL = 200


def _load_history() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _tail_file(path: str, n: int = DEFAULT_TAIL) -> str:
    if not os.path.exists(path):
        return f"[File not found: {path}]"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-n:]) if len(lines) > n else "".join(lines)
    except Exception as e:
        return f"[Error reading file: {e}]"


def _search_order_id(order_id: str) -> str:
    """Search all log files for lines mentioning order_id."""
    results = []
    if not os.path.isdir(LOG_DIR):
        return f"[Log directory not found: {LOG_DIR}]"
    for fname in sorted(os.listdir(LOG_DIR)):
        if not fname.endswith(".log"):
            continue
        fpath = os.path.join(LOG_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                matched = [line for line in f if order_id in line]
            if matched:
                results.append(f"=== {fname} ===")
                results.extend(l.rstrip() for l in matched)
        except Exception:
            continue
    if not results:
        return f"[No log lines found for order_id: {order_id}]"
    return "\n".join(results)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default access log spam

    def _respond(self, status: int, body: str):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        def p(key):
            return params.get(key, [None])[0]

        tail = int(p("tail") or DEFAULT_TAIL)

        if parsed.path == "/log":
            order_id = p("order_id")
            session_id = p("session_id")
            file_path = p("file")

            if order_id:
                self._respond(200, _search_order_id(order_id))

            elif session_id:
                sessions = _load_history()
                s = next((x for x in sessions if x["id"] == session_id), None)
                if not s:
                    self._respond(404, f"Session not found: {session_id}")
                    return
                log_path = s.get("log_path", "")
                self._respond(200, _tail_file(log_path, tail))

            elif file_path:
                # Restrict to logs/ directory for safety
                abs_path = os.path.abspath(file_path)
                abs_log_dir = os.path.abspath(LOG_DIR)
                if not abs_path.startswith(abs_log_dir):
                    self._respond(403, "Access denied: only files in logs/ allowed")
                    return
                self._respond(200, _tail_file(abs_path, tail))

            else:
                self._respond(400, "Missing param: order_id, session_id, or file")

        elif parsed.path == "/sessions":
            sessions = _load_history()
            # Return compact summary
            summary = []
            for s in reversed(sessions):
                summary.append({
                    "id": s["id"],
                    "name": s.get("name"),
                    "symbol": s["symbol"],
                    "mode": s["mode"],
                    "started_at": s["started_at"],
                    "stopped_at": s.get("stopped_at"),
                    "stats": s.get("stats", {}),
                    "log_path": s.get("log_path", ""),
                    "deleted": s.get("deleted", False),
                })
            self._respond(200, json.dumps(summary, indent=2, ensure_ascii=False))

        else:
            self._respond(404, f"Unknown endpoint: {parsed.path}\n\n"
                              "Available:\n"
                              "  GET /log?order_id=ORD-xxx\n"
                              "  GET /log?session_id=xxx\n"
                              "  GET /log?file=logs/bot_xxx.log[&tail=200]\n"
                              "  GET /sessions\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8502)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    # Change to project root so relative paths (logs/, data/) work
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    server = HTTPServer((args.host, args.port), Handler)
    print(f"API server running on http://{args.host}:{args.port}", flush=True)
    print("Endpoints: /log?order_id=... | /log?session_id=... | /sessions", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
