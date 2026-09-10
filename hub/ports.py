"""Ports: one plugged (bot, room) pair."""

from __future__ import annotations

import re
import time
from pathlib import Path

from . import auth
from .store import default_data_dir, ensure_dir, read_json, write_json

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


class PortError(ValueError):
    pass


def _ports_path(data_dir: Path | None = None) -> Path:
    return (data_dir or default_data_dir()) / "ports.json"


def load_all(data_dir: Path | None = None) -> dict:
    raw = read_json(_ports_path(data_dir), {"ports": []})
    ports = raw.get("ports") or []
    return {p["id"]: p for p in ports if p.get("id")}


def save_all(ports: dict, data_dir: Path | None = None) -> None:
    rows = [ports[k] for k in sorted(ports)]
    write_json(_ports_path(data_dir), {"ports": rows})


def get(port_id: str, data_dir: Path | None = None) -> dict:
    ports = load_all(data_dir)
    if port_id not in ports:
        raise PortError("unknown port: %s" % port_id)
    return ports[port_id]


def find_by_token(token: str, data_dir: Path | None = None) -> dict | None:
    if not token:
        return None
    for port in load_all(data_dir).values():
        if port.get("revoked"):
            continue
        if auth.equal(token, port.get("token") or ""):
            return port
    return None


def create(
    name: str,
    adapter: str = "agensis",
    data_dir: Path | None = None,
    adapter_config: dict | None = None,
) -> dict:
    slug = name.strip().lower().replace(" ", "-")
    if not SLUG_RE.match(slug):
        raise PortError("port name must be slug-like (letters, digits, _-)")
    ports = load_all(data_dir)
    port_id = "p_" + slug
    if port_id in ports and not ports[port_id].get("revoked"):
        raise PortError("port already exists: %s" % port_id)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    port = {
        "id": port_id,
        "name": name.strip(),
        "adapter": adapter,
        "token": auth.new_port_token(),
        "created_at": now,
        "revoked": False,
        "webhook_url": "",
        "webhook_auth": "",
        "adapter_config": adapter_config or {},
        "last_seen_at": None,
        "presence": "unplugged",
    }
    ports[port_id] = port
    save_all(ports, data_dir)
    ensure_dir((data_dir or default_data_dir()) / "mailbox" / port_id)
    return port


def update(port_id: str, fields: dict, data_dir: Path | None = None) -> dict:
    ports = load_all(data_dir)
    if port_id not in ports:
        raise PortError("unknown port: %s" % port_id)
    ports[port_id].update(fields)
    save_all(ports, data_dir)
    return ports[port_id]


def set_webhook(port_id: str, url: str, auth_header: str, data_dir: Path | None = None) -> dict:
    return update(
        port_id,
        {"webhook_url": (url or "").strip(), "webhook_auth": (auth_header or "").strip()},
        data_dir,
    )


def set_adapter_config(port_id: str, config: dict, data_dir: Path | None = None) -> dict:
    port = get(port_id, data_dir)
    merged = dict(port.get("adapter_config") or {})
    merged.update(config)
    return update(port_id, {"adapter_config": merged}, data_dir)


def revoke(port_id: str, data_dir: Path | None = None) -> dict:
    return update(port_id, {"revoked": True, "presence": "unplugged", "token": auth.new_port_token()}, data_dir)


def public_view(port: dict) -> dict:
    cfg = dict(port.get("adapter_config") or {})
    if "token" in cfg:
        raw = cfg["token"] or ""
        cfg["token"] = (raw[:7] + "\u2026" + raw[-4:]) if len(raw) > 12 else "(set)" if raw else ""
    return {
        "id": port.get("id"),
        "name": port.get("name"),
        "adapter": port.get("adapter"),
        "created_at": port.get("created_at"),
        "revoked": bool(port.get("revoked")),
        "webhook_set": bool(port.get("webhook_url")),
        "presence": port.get("presence"),
        "last_seen_at": port.get("last_seen_at"),
        "adapter_config": cfg,
    }
