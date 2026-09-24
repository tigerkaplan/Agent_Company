"""Small localhost-only HTTP adapter for webhook ingress."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Mapping

from runtime.webhooks.models import WebhookResultStatus
from runtime.webhooks.service import WebhookIngressService


@dataclass(frozen=True)
class WebhookHttpResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]


class WebhookHttpAdapter:
    _PATH = re.compile(r"/webhooks/([A-Za-z0-9][A-Za-z0-9._-]{0,63})\Z")

    def __init__(self, service: WebhookIngressService) -> None:
        self.service = service

    def handle(
        self,
        *,
        method: str,
        path: str,
        headers: Mapping[str, str],
        body: bytes,
    ) -> WebhookHttpResponse:
        if method != "POST":
            return self._response(405, {"status": "rejected", "error_code": "method_not_allowed"})
        match = self._PATH.fullmatch(path)
        if match is None:
            return self._response(404, {"status": "rejected", "error_code": "not_found"})
        normalized = {key.lower(): value for key, value in headers.items()}
        content_type = normalized.get("content-type", "").lower().replace(" ", "")
        if content_type not in {"application/json", "application/json;charset=utf-8"}:
            return self._response(
                415, {"status": "rejected", "error_code": "unsupported_content_type"}
            )
        if len(body) > self.service.config.max_request_bytes:
            return self._response(
                413, {"status": "rejected", "error_code": "request_too_large"}
            )
        result = self.service.ingest(
            source_id=match.group(1),
            raw_body=body,
            signature=normalized.get("x-agent-webhook-signature"),
            signed_timestamp=normalized.get("x-agent-webhook-timestamp"),
        )
        status_code = 202
        if result.status is WebhookResultStatus.DUPLICATE:
            status_code = 200
        elif result.status is WebhookResultStatus.FAILED:
            status_code = 503
        elif result.status is WebhookResultStatus.REJECTED:
            status_code = {
                "request_too_large": 413,
                "unknown_source": 401,
                "disabled_source": 403,
                "invalid_signature": 401,
                "stale_timestamp": 401,
                "unsupported_event_type": 422,
                "project_binding_mismatch": 422,
                "idempotency_conflict": 409,
                "invalid_event": 422,
            }.get(result.error_code, 400)
        return self._response(status_code, result.to_dict())

    @staticmethod
    def _response(status_code: int, value: dict[str, object]) -> WebhookHttpResponse:
        body = json.dumps(value, sort_keys=True, ensure_ascii=True).encode("utf-8")
        return WebhookHttpResponse(
            status_code=status_code,
            body=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": str(len(body)),
                "Cache-Control": "no-store",
            },
        )


def create_local_http_server(
    service: WebhookIngressService,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    request_timeout_seconds: float = 5.0,
) -> HTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Webhook HTTP adapter may bind only to localhost")
    if not 0 <= port <= 65535:
        raise ValueError("Webhook HTTP port is invalid")
    if not 0.1 <= request_timeout_seconds <= 30:
        raise ValueError("Webhook HTTP request timeout is outside 0.1-30 seconds")
    adapter = WebhookHttpAdapter(service)
    maximum = service.config.max_request_bytes

    class Handler(BaseHTTPRequestHandler):
        server_version = "AgentCompanyWebhook/1"
        sys_version = ""

        def do_POST(self) -> None:
            self.connection.settimeout(request_timeout_seconds)
            if self.headers.get("Transfer-Encoding") is not None:
                self._send(
                    WebhookHttpAdapter._response(
                        400,
                        {"status": "rejected", "error_code": "invalid_transfer_encoding"},
                    )
                )
                return
            try:
                content_length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                content_length = -1
            if content_length < 0:
                self._send(
                    WebhookHttpAdapter._response(
                        411, {"status": "rejected", "error_code": "length_required"}
                    )
                )
                return
            if content_length > maximum:
                self._send(
                    WebhookHttpAdapter._response(
                        413, {"status": "rejected", "error_code": "request_too_large"}
                    )
                )
                return
            try:
                body = self.rfile.read(content_length)
            except (OSError, TimeoutError):
                self._send(
                    WebhookHttpAdapter._response(
                        408, {"status": "rejected", "error_code": "request_timeout"}
                    )
                )
                return
            if len(body) != content_length:
                self._send(
                    WebhookHttpAdapter._response(
                        400, {"status": "rejected", "error_code": "incomplete_body"}
                    )
                )
                return
            response = adapter.handle(
                method="POST",
                path=self.path,
                headers=dict(self.headers.items()),
                body=body,
            )
            self._send(response)

        def do_GET(self) -> None:
            self._send(adapter.handle(method="GET", path=self.path, headers={}, body=b""))

        def _send(self, response: WebhookHttpResponse) -> None:
            self.send_response(response.status_code)
            for name, value in response.headers.items():
                self.send_header(name, value)
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(response.body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer((host, port), Handler)
    server.timeout = request_timeout_seconds
    return server
