"""HTTP front door: /mcp for Grok Bot, /admin for the operator, /health."""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import auth, mcp_protocol, ports
from .store import default_data_dir

log = logging.getLogger("gch.http")


def make_handler(runtime, admin_token: str, public_base: str):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            log.info("%s - " + fmt, self.address_string(), *args)

        def _read_json(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            if length > 2_000_000:
                raise ValueError("payload too large")
            raw = self.rfile.read(length)
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

        def _send(self, code: int, payload, extra_headers=None):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for key, value in (extra_headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _send_empty(self, code: int):
            self.send_response(code)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _admin(self) -> bool:
            token = auth.bearer_from_header(self.headers.get("Authorization") or "")
            if not admin_token or not auth.equal(token, admin_token):
                self._send(401, {"error": "admin token required"})
                return False
            return True

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Allow", "GET, POST, OPTIONS")
            self.end_headers()

        def do_GET(self):
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path == "/health":
                self._send(200, {"ok": True, "service": "grokbot-connector-hub"})
                return
            if path == "/admin/ports":
                if not self._admin():
                    return
                rows = [ports.public_view(p) for p in ports.load_all(runtime.data_dir).values()]
                self._send(200, {"ports": rows})
                return
            self._send(404, {"error": "not found"})

        def do_POST(self):
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path in ("/mcp", "/backend/mcp"):
                self._mcp()
                return
            if path == "/admin/ports":
                self._create_port()
                return
            if path.startswith("/admin/ports/"):
                self._port_action(path)
                return
            self._send(404, {"error": "not found"})

        def _mcp(self):
            token = auth.bearer_from_header(self.headers.get("Authorization") or "")
            port = ports.find_by_token(token, runtime.data_dir)
            if port is None:
                self._send(
                    401,
                    {"error": "unauthorized"},
                    extra_headers={"WWW-Authenticate": 'Bearer realm="gch"'},
                )
                return
            try:
                message = self._read_json()
            except (ValueError, json.JSONDecodeError):
                self._send(400, {"error": "invalid json"})
                return
            reply = mcp_protocol.handle_rpc(message, port, runtime)
            if reply is None:
                self._send_empty(202)
                return
            self._send(200, reply)

        def _create_port(self):
            if not self._admin():
                return
            try:
                body = self._read_json()
                port = ports.create(
                    body.get("name") or "",
                    adapter=body.get("adapter") or "agensis",
                    data_dir=runtime.data_dir,
                )
            except (ports.PortError, ValueError, json.JSONDecodeError) as err:
                self._send(400, {"error": str(err)})
                return
            self._send(201, _pairing_payload(port, public_base))

        def _port_action(self, path: str):
            if not self._admin():
                return
            parts = path.strip("/").split("/")
            if len(parts) < 3:
                self._send(404, {"error": "not found"})
                return
            port_id = parts[2]
            action = parts[3] if len(parts) > 3 else ""
            try:
                body = self._read_json()
            except (ValueError, json.JSONDecodeError):
                self._send(400, {"error": "invalid json"})
                return
            try:
                if action == "webhook":
                    port = ports.set_webhook(
                        port_id,
                        body.get("url") or "",
                        body.get("auth") or body.get("authorization") or "",
                        runtime.data_dir,
                    )
                    self._send(200, ports.public_view(port))
                    return
                if action == "agensis":
                    port = ports.set_adapter_config(
                        port_id,
                        {
                            "mcp_url": body.get("mcp_url") or "",
                            "token": body.get("token") or "",
                            "poll_seconds": body.get("poll_seconds") or 3,
                            "job_budget_seconds": body.get("job_budget_seconds") or 480,
                        },
                        runtime.data_dir,
                    )
                    runtime.attach(port_id)
                    self._send(200, ports.public_view(port))
                    return
                if action == "demo-job":
                    job = runtime.inject_mock(
                        port_id,
                        body.get("prompt") or "Say hello from the hub demo.",
                        job_id=body.get("job_id") or "demo-1",
                    )
                    self._send(200, {"ok": True, "job": {"id": job["id"], "status": job["status"]}})
                    return
                if action == "revoke":
                    port = ports.revoke(port_id, runtime.data_dir)
                    self._send(200, ports.public_view(port))
                    return
            except (ports.PortError, RuntimeError) as err:
                self._send(400, {"error": str(err)})
                return
            self._send(404, {"error": "not found"})

    return Handler


def _pairing_payload(port: dict, public_base: str) -> dict:
    base = public_base.rstrip("/")
    return {
        "port": ports.public_view(port),
        "token": port["token"],
        "connector_url": base + "/mcp",
        "instructions": [
            "Add a custom MCP connector in Grok Bot pointing at connector_url.",
            "Use the port token as the Bearer credential. Never paste the Agensis aga_ token into Grok Bot.",
            "Create a webhook routine from prompts/GROK_BOT_ROUTINE.md.",
            "Register that routine URL + crsr_ key with: gch port-webhook %s --url URL --auth KEY" % port["id"],
        ],
    }


def serve(host: str, port: int, runtime, admin_token: str, public_base: str):
    httpd = ThreadingHTTPServer((host, port), make_handler(runtime, admin_token, public_base))
    log.info("hub listening on http://%s:%s  mcp=%s/mcp", host, port, public_base.rstrip("/"))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("stopping")
    finally:
        httpd.server_close()
        runtime.stop()


def default_public_base(host: str, port: int) -> str:
    shown = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    return "http://%s:%s" % (shown, port)


_ = default_data_dir
