"""Simple web UI for viewing IP update history.

Stdlib-only HTTP server (no runtime dependencies). Serves a single-page
HTML table of the JSONL log file, protected by a session cookie login.
"""

from __future__ import annotations

import html
import http.server
import json
import secrets
import time
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional

from gddynu.config import Config

# token -> expiry (unix timestamp); shared across threads via CPython GIL
_sessions: Dict[str, float] = {}
_SESSION_TTL = 8 * 3600  # 8 hours


class _Handler(http.server.BaseHTTPRequestHandler):
    config: Config  # attached as class attribute by run_web()

    def log_message(self, fmt: str, *args: object) -> None:  # type: ignore[override]
        pass  # suppress per-request noise to stdout

    # ------------------------------------------------------------------
    # Cookie / session helpers
    # ------------------------------------------------------------------

    def _get_cookie(self, name: str) -> Optional[str]:
        for part in self.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k.strip() == name:
                return v.strip()
        return None

    def _is_logged_in(self) -> bool:
        token = self._get_cookie("session")
        if not token:
            return False
        expiry = _sessions.get(token, 0.0)
        if time.time() > expiry:
            _sessions.pop(token, None)
            return False
        return True

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    def _send_html(self, status: int, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    # ------------------------------------------------------------------
    # Request handlers
    # ------------------------------------------------------------------

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/login":
            self._send_html(200, _render_login())
        elif path == "/logout":
            token = self._get_cookie("session")
            if token:
                _sessions.pop(token, None)
            self.send_response(302)
            self.send_header(
                "Set-Cookie",
                "session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict",
            )
            self.send_header("Location", "/login")
            self.end_headers()
        elif path == "/":
            if not self._is_logged_in():
                self._redirect("/login")
                return
            self._send_html(200, _render_table(self.config.log_file))
        else:
            self._send_html(404, "<h1>404 Not Found</h1>")

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path != "/login":
            self._send_html(404, "<h1>404 Not Found</h1>")
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        params = urllib.parse.parse_qs(body)
        username = params.get("username", [""])[0]
        password = params.get("password", [""])[0]

        cfg = self.config
        ok = secrets.compare_digest(username, cfg.web_username) and secrets.compare_digest(
            password, cfg.web_password
        )
        if ok:
            token = secrets.token_hex(32)
            _sessions[token] = time.time() + _SESSION_TTL
            self.send_response(302)
            self.send_header(
                "Set-Cookie",
                f"session={token}; Max-Age={_SESSION_TTL}; Path=/; HttpOnly; SameSite=Strict",
            )
            self.send_header("Location", "/")
            self.end_headers()
        else:
            self._send_html(200, _render_login(error=True))


# ----------------------------------------------------------------------
# HTML rendering
# ----------------------------------------------------------------------

_CSS_COMMON = """
*, *::before, *::after { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, sans-serif; background: #f0f2f5; margin: 0; padding: 0; }
"""

_CSS_LOGIN = """
body { display: flex; justify-content: center; align-items: center; min-height: 100vh; }
.card { background: #fff; padding: 2rem 2.5rem; border-radius: 8px;
        box-shadow: 0 2px 12px rgba(0,0,0,.12); width: 320px; }
h1 { margin: 0 0 1.5rem; font-size: 1.25rem; color: #1a1a2e; }
label { display: block; font-size: .875rem; color: #555; margin-bottom: .25rem; }
input { width: 100%; padding: .5rem .75rem; border: 1px solid #ccc; border-radius: 4px;
        font-size: 1rem; margin-bottom: 1rem; }
input:focus { outline: 2px solid #2563eb; border-color: transparent; }
button { width: 100%; padding: .6rem; background: #2563eb; color: #fff;
         border: none; border-radius: 4px; font-size: 1rem; cursor: pointer; }
button:hover { background: #1d4ed8; }
.error { color: #dc2626; font-size: .875rem; margin-bottom: 1rem; }
"""

_CSS_TABLE = """
body { padding: 1rem; }
header { display: flex; justify-content: space-between; align-items: center;
         background: #1a1a2e; color: #fff; padding: .75rem 1.25rem;
         border-radius: 8px; margin-bottom: 1rem; }
header h1 { margin: 0; font-size: 1.1rem; }
header a { color: #93c5fd; font-size: .875rem; text-decoration: none; }
header a:hover { text-decoration: underline; }
.meta { font-size: .8rem; color: #666; margin-bottom: .5rem; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; background: #fff;
        border-radius: 8px; overflow: hidden;
        box-shadow: 0 1px 6px rgba(0,0,0,.08); font-size: .875rem; }
th { background: #1a1a2e; color: #fff; padding: .6rem .75rem;
     text-align: left; font-weight: 600; white-space: nowrap; }
td { padding: .5rem .75rem; border-bottom: 1px solid #e5e7eb; white-space: nowrap; }
tr:last-child td { border-bottom: none; }
tr.changed td { background: #f0fdf4; }
tr.err td { background: #fef2f2; }
tr:not(.changed):not(.err):hover td { background: #f9fafb; }
tr.changed:hover td { background: #dcfce7; }
tr.err:hover td { background: #fee2e2; }
.legend { font-size: .78rem; color: #666; margin-top: .5rem;
          display: flex; gap: 1rem; }
.legend span { display: inline-flex; align-items: center; gap: .3rem; }
.dot { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.dot-green { background: #86efac; }
.dot-red { background: #fca5a5; }
"""


def _page(title: str, extra_css: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="hu">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{_CSS_COMMON}{extra_css}</style>\n"
        "</head>\n"
        f"<body>{body}</body>\n"
        "</html>"
    )


def _render_login(error: bool = False) -> str:
    err_html = '<p class="error">Helytelen felhasználónév vagy jelszó.</p>' if error else ""
    body = (
        '<div class="card">'
        "<h1>gddynu IP History</h1>"
        f"{err_html}"
        '<form method="post" action="/login">'
        '<label for="u">Felhasználónév</label>'
        '<input id="u" type="text" name="username" autocomplete="username" required>'
        '<label for="p">Jelszó</label>'
        '<input id="p" type="password" name="password" autocomplete="current-password" required>'
        '<button type="submit">Belépés</button>'
        "</form>"
        "</div>"
    )
    return _page("gddynu – Belépés", _CSS_LOGIN, body)


def _read_log(log_file: str) -> List[dict]:
    p = Path(log_file)
    if not p.is_file():
        return []
    records: List[dict] = []
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    records.reverse()  # newest first
    return records


def _fmt_ts(ts: str) -> str:
    """'2026-06-19T10:00:00.123+00:00' -> '2026-06-19 10:00:00 UTC'"""
    ts = ts.split(".")[0]          # drop microseconds
    ts = ts.replace("+00:00", "") # drop timezone suffix
    return ts.replace("T", " ") + " UTC"


def _render_table(log_file: str) -> str:
    records = _read_log(log_file)

    rows: List[str] = []
    for r in records:
        action = r.get("action") or ""
        changed = bool(r.get("changed"))
        if action == "error":
            row_cls = "err"
        elif changed:
            row_cls = "changed"
        else:
            row_cls = ""

        ts = _fmt_ts(r.get("ts", ""))
        ipv4 = html.escape(r.get("ipv4") or "—")
        ipv6 = html.escape(r.get("ipv6") or "—")
        changed_lbl = "igen" if changed else "nem"
        action_lbl = html.escape(action or "—")
        result_lbl = html.escape(r.get("result") or "—")

        rows.append(
            f'<tr class="{row_cls}">'
            f"<td>{ts}</td><td>{ipv4}</td><td>{ipv6}</td>"
            f"<td>{changed_lbl}</td><td>{action_lbl}</td><td>{result_lbl}</td>"
            "</tr>"
        )

    rows_html = "\n".join(rows) if rows else '<tr><td colspan="6">Nincs adat.</td></tr>'
    count = len(records)

    body = (
        "<header>"
        "<h1>gddynu IP History</h1>"
        '<a href="/logout">Kilépés</a>'
        "</header>"
        f'<p class="meta">{count} bejegyzés &nbsp;·&nbsp; legújabb elöl</p>'
        '<div class="table-wrap">'
        "<table>"
        "<thead><tr>"
        "<th>Időpont (UTC)</th><th>IPv4</th><th>IPv6</th>"
        "<th>Változott</th><th>Akció</th><th>Eredmény</th>"
        "</tr></thead>"
        f"<tbody>\n{rows_html}\n</tbody>"
        "</table>"
        "</div>"
        '<div class="legend">'
        '<span><span class="dot dot-green"></span> IP változott</span>'
        '<span><span class="dot dot-red"></span> Hiba</span>'
        "</div>"
    )
    return _page("gddynu – IP History", _CSS_TABLE, body)


# ----------------------------------------------------------------------
# Server entry point
# ----------------------------------------------------------------------

def run_web(config: Config) -> None:
    """Start the HTTP server. Blocks until Ctrl+C / SIGINT."""
    if not config.web_username or not config.web_password:
        raise ValueError(
            "web_username and web_password must be set in config or via "
            "GDDYNU_WEB_USERNAME / GDDYNU_WEB_PASSWORD environment variables."
        )

    # Bind config to handler via a new subclass (avoids global state).
    handler_cls = type("_BoundHandler", (_Handler,), {"config": config})

    server = http.server.ThreadingHTTPServer(
        (config.web_host, config.web_port), handler_cls
    )
    print(
        f"gddynu web UI indítva: http://{config.web_host}:{config.web_port}/ "
        f"(log: {config.log_file})"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
