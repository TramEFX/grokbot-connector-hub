"""Minimal Streamable-HTTP JSON-RPC MCP server for Grok Bot connectors.

Intentionally small: initialize, tools/list, tools/call, notifications/initialized.
Grok Bot is the MCP client. The harness never talks to this surface.
"""

from __future__ import annotations

import json

from . import __version__, mailbox, ports

PROTOCOL = "2025-03-26"

TOOLS = [
    {
        "name": "hub_whoami",
        "description": "Return this port: id, name, adapter, presence, open job count.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "hub_inbox",
        "description": (
            "List open harness turns for this port, oldest first. "
            "Each item has id, prompt, session_id, deadline_seconds. "
            "The prompt is already composed — pass it through; do not re-wrap. "
            "Ignore webhook bodies; this mailbox is the source of truth."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "mark_read": {"type": "boolean", "description": "Unused; replies go through hub_reply."}
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "hub_reply",
        "description": "Post the Grok Bot turn as this port's reply and deliver it to the harness.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["job_id", "text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "hub_fail",
        "description": "Fail an open job so the room resumes instead of hanging.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string"},
                "error": {"type": "string"},
            },
            "required": ["job_id"],
            "additionalProperties": False,
        },
    },
]


def handle_rpc(message: dict, port: dict, runtime) -> dict | None:
    method = message.get("method")
    req_id = message.get("id")
    if method is None:
        return _err(req_id, -32600, "invalid request")
    if req_id is None and str(method).startswith("notifications/"):
        return None
    if method == "initialize":
        return _ok(
            req_id,
            {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "grokbot-connector-hub", "version": __version__},
            },
        )
    if method in ("tools/list", "tools/listChanged"):
        return _ok(req_id, {"tools": TOOLS})
    if method == "ping":
        return _ok(req_id, {})
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            result = dispatch_tool(name, args, port, runtime)
        except mailbox.MailboxError as err:
            return _ok(req_id, _tool_text({"ok": False, "error": str(err)}, is_error=True))
        except Exception as err:  # noqa: BLE001
            return _ok(req_id, _tool_text({"ok": False, "error": str(err)[:300]}, is_error=True))
        return _ok(req_id, _tool_text(result))
    return _err(req_id, -32601, "method not found: %s" % method)


def dispatch_tool(name: str, args: dict, port: dict, runtime) -> dict:
    data_dir = runtime.data_dir
    if name == "hub_whoami":
        mailbox.expire_open(port["id"], data_dir)
        view = ports.public_view(port)
        view["open_jobs"] = len(mailbox.list_open(port["id"], data_dir))
        view["ok"] = True
        return view
    if name == "hub_inbox":
        mailbox.expire_open(port["id"], data_dir)
        now = __import__("time").time()
        items = []
        for row in mailbox.list_open(port["id"], data_dir):
            items.append(
                {
                    "id": row["id"],
                    "prompt": row.get("prompt") or "",
                    "session_id": row.get("session_id"),
                    "deadline_seconds": max(0, int((row.get("deadline_at") or now) - now)),
                }
            )
        return {"ok": True, "jobs": items}
    if name == "hub_reply":
        record = mailbox.reply(port["id"], args.get("job_id"), args.get("text"), data_dir)
        runtime.deliver_reply(port, record)
        return {"ok": True, "id": record["id"], "status": "replied"}
    if name == "hub_fail":
        record = mailbox.fail(port["id"], args.get("job_id"), args.get("error") or "failed", data_dir)
        runtime.deliver_fail(port, record)
        return {"ok": True, "id": record["id"], "status": "failed"}
    raise mailbox.MailboxError("unknown tool: %s" % name)


def _tool_text(payload: dict, is_error: bool = False) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(payload)}],
        "isError": is_error,
    }


def _ok(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
