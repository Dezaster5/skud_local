from __future__ import annotations

import base64
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


RELAY_HOST = os.getenv("FONDVISION_RELAY_HOST", "0.0.0.0")
RELAY_PORT = int(os.getenv("FONDVISION_RELAY_PORT", "8099"))
RELAY_TOKEN = os.getenv("FONDVISION_RELAY_TOKEN", "")


class FondvisionRelayHandler(BaseHTTPRequestHandler):
    server_version = "FondvisionRelay/1.0"

    def do_GET(self) -> None:
        if self.path != "/health":
            self._write_json(HTTPStatus.NOT_FOUND, {"status": "error", "error": "not_found"})
            return

        self._write_json(HTTPStatus.OK, {"status": "ok"})

    def do_POST(self) -> None:
        if self.path != "/open-door":
            self._write_json(HTTPStatus.NOT_FOUND, {"status": "error", "error": "not_found"})
            return

        if RELAY_TOKEN:
            provided_token = self.headers.get("X-Relay-Token", "")
            if provided_token != RELAY_TOKEN:
                self._write_json(HTTPStatus.FORBIDDEN, {"status": "error", "error": "forbidden"})
                return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"status": "error", "error": "invalid_content_length"})
            return

        try:
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._write_json(HTTPStatus.BAD_REQUEST, {"status": "error", "error": "invalid_json"})
            return

        controller_ip = str(payload.get("controller_ip", "")).strip()
        direction = payload.get("direction")
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", "")).strip()
        timeout_seconds = int(payload.get("timeout_seconds", 12))

        if not controller_ip or direction not in (0, 1) or not username or not password:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "error", "error": "missing_required_fields"},
            )
            return

        result_status, result_payload = self._open_door(
            controller_ip=controller_ip,
            direction=direction,
            username=username,
            password=password,
            timeout_seconds=timeout_seconds,
        )
        self._write_json(result_status, result_payload)

    def log_message(self, format: str, *args) -> None:
        return

    def _open_door(
        self,
        *,
        controller_ip: str,
        direction: int,
        username: str,
        password: str,
        timeout_seconds: int,
    ) -> tuple[HTTPStatus, dict[str, object]]:
        query = urlencode({"DIR": str(direction)})
        url = f"http://{controller_ip}/cgi-bin/command?{query}"
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        request = Request(
            url,
            headers={
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                response_bytes = response.read()
                return HTTPStatus.OK, {
                    "status": "ok",
                    "controller_status": response.status,
                    "controller_response": response_bytes.decode("latin-1", errors="replace"),
                }
        except HTTPError as exc:
            response_text = exc.read().decode("latin-1", errors="replace")
            return HTTPStatus.BAD_GATEWAY, {
                "status": "error",
                "error": str(exc),
                "controller_status": exc.code,
                "controller_response": response_text,
            }
        except URLError as exc:
            return HTTPStatus.BAD_GATEWAY, {
                "status": "error",
                "error": str(exc.reason),
                "controller_status": None,
                "controller_response": "",
            }

    def _write_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer((RELAY_HOST, RELAY_PORT), FondvisionRelayHandler)
    print(f"Fondvision relay listening on http://{RELAY_HOST}:{RELAY_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
