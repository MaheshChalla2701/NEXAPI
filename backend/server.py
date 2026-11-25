"""Standard-library HTTP server for the analytics API (no web framework).

    python3 -m backend.server            # http://127.0.0.1:8000

Serves /api/* from the SQLite database (read-only) and, if the frontend has
been built, the React app from frontend/dist.
"""

from __future__ import annotations

import json
import logging
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from backend import api, db
from backend.analyst import engine, local_engine
from backend.config import Settings, load_settings

log = logging.getLogger("backend")
MAX_BODY_BYTES = 8 * 1024


class Handler(BaseHTTPRequestHandler):
    settings: Settings  # set by make_server
    server_version = "RevenueAnalytics/0.1"
    sys_version = ""

    # ---- dispatch ---------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            self._api("GET")
        else:
            self._static(path)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path.startswith("/api/"):
            self._api("POST")
        else:
            self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "Method not allowed"})

    def _api(self, method: str) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            status, payload = self._route(method, parsed.path, query)
        except api.ApiError as exc:
            status, payload = exc.status, {"error": exc.message}
        except db.DatabaseUnavailable as exc:
            status, payload = HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc), "code": "database_unavailable"}
        except Exception:  # never leak internals to the client
            log.exception("Unhandled error for %s %s", method, parsed.path)
            status, payload = HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Internal server error"}
        self._json(status, payload)

    def _route(self, method: str, path: str, query: dict) -> tuple[int, dict]:
        s = self.settings
        if method == "GET" and path == "/api/health":
            return HTTPStatus.OK, {"status": "ok", "database": s.db_path.is_file()}
        if method == "GET" and path == "/api/meta":
            with db.connect(s.db_path) as conn:
                return HTTPStatus.OK, {"meta": api.meta(conn), "analyst": s.public_view()}
        if method == "GET" and path in api.ENDPOINTS:
            with db.connect(s.db_path) as conn:
                return HTTPStatus.OK, {"meta": api.meta(conn), "data": api.ENDPOINTS[path](conn, query)}
        if method == "GET" and path == "/api/analyst/status":
            return HTTPStatus.OK, s.public_view()
        if method == "GET" and path == "/api/analyst/suggestions":
            return HTTPStatus.OK, {"suggestions": local_engine.SUGGESTIONS}
        if method == "POST" and path == "/api/analyst/ask":
            question, mode = self._read_question()
            with db.connect(s.db_path) as conn:
                return HTTPStatus.OK, engine.ask(conn, s, question, mode)
        known = set(api.ENDPOINTS) | {"/api/health", "/api/meta", "/api/analyst/status",
                                      "/api/analyst/suggestions", "/api/analyst/ask"}
        if path in known:
            raise api.ApiError(HTTPStatus.METHOD_NOT_ALLOWED, f"{method} not allowed on {path}")
        raise api.ApiError(HTTPStatus.NOT_FOUND, f"Unknown endpoint {path}")

    def _read_question(self) -> tuple[str, str]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise api.ApiError(HTTPStatus.BAD_REQUEST, "Invalid Content-Length") from None
        if length <= 0 or length > MAX_BODY_BYTES:
            raise api.ApiError(HTTPStatus.BAD_REQUEST, f"Body must be 1-{MAX_BODY_BYTES} bytes of JSON")
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            raise api.ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json")
        try:
            body = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise api.ApiError(HTTPStatus.BAD_REQUEST, "Body is not valid JSON") from None
        if not isinstance(body, dict):
            raise api.ApiError(HTTPStatus.BAD_REQUEST, "Body must be a JSON object")
        question = body.get("question")
        if not isinstance(question, str) or not question.strip():
            raise api.ApiError(HTTPStatus.BAD_REQUEST, "'question' must be a non-empty string")
        question = question.strip()
        if len(question) > engine.MAX_QUESTION_CHARS:
            raise api.ApiError(HTTPStatus.BAD_REQUEST, f"'question' is limited to {engine.MAX_QUESTION_CHARS} characters")
        mode = body.get("mode", "auto")
        if mode not in engine.MODES:
            raise api.ApiError(HTTPStatus.BAD_REQUEST, f"'mode' must be one of {', '.join(engine.MODES)}")
        return question, mode

    # ---- responses --------------------------------------------------------
    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _static(self, path: str) -> None:
        root = self.settings.static_dir.resolve()
        if not (root / "index.html").is_file():
            self._json(HTTPStatus.NOT_FOUND, {
                "error": "Frontend not built. Run the Vite dev server (cd frontend && npm run dev) "
                         "or build it (npm run build) to serve it from here."})
            return
        target = (root / path.lstrip("/")).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            target = root / "index.html"  # SPA fallback; also blocks path traversal
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        log.info("%s %s", self.address_string(), fmt % args)


def make_server(settings: Settings) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"settings": settings})
    return ThreadingHTTPServer((settings.host, settings.port), handler)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = load_settings()
    server = make_server(settings)
    mode = "external (" + settings.external_model + ")" if settings.external_ready else "local"
    log.info("API on http://%s:%s  db=%s  analyst=%s", settings.host, settings.port, settings.db_path, mode)
    if not settings.db_path.is_file():
        log.warning("Database missing. Build it: python3 -m pipeline.build_db --source mock")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
