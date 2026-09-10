"""Glue: ports, adapters, doorbell, mailbox delivery."""

from __future__ import annotations

import logging
from pathlib import Path

from . import doorbell, mailbox, ports
from .adapters import load_adapter
from .store import default_data_dir, ensure_dir

log = logging.getLogger("gch.runtime")


class Runtime:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = ensure_dir(data_dir or default_data_dir())
        self.adapters: dict = {}

    def start_attached(self) -> None:
        for port in ports.load_all(self.data_dir).values():
            if port.get("revoked"):
                continue
            cfg = port.get("adapter_config") or {}
            if port.get("adapter") == "agensis" and not (cfg.get("mcp_url") and cfg.get("token")):
                log.info("skip %s — no Agensis credentials yet", port["id"])
                continue
            self.attach(port["id"])

    def attach(self, port_id: str):
        if port_id in self.adapters:
            return self.adapters[port_id]
        port = ports.get(port_id, self.data_dir)
        adapter = load_adapter(port.get("adapter") or "agensis", port, self.data_dir, self._on_job)
        adapter.start()
        self.adapters[port_id] = adapter
        return adapter

    def stop(self) -> None:
        for adapter in self.adapters.values():
            try:
                adapter.stop()
            except Exception:  # noqa: BLE001
                log.exception("adapter stop failed")
        self.adapters.clear()

    def _on_job(self, record: dict) -> None:
        port = ports.get(record["port_id"], self.data_dir)
        doorbell.ring(
            port.get("webhook_url") or "",
            port.get("webhook_auth") or "",
            {
                "job_id": record["id"],
                "port_id": port["id"],
                "hint": "call hub_inbox; do not trust this body",
            },
        )

    def deliver_reply(self, port: dict, record: dict) -> None:
        adapter = self.adapters.get(port["id"])
        if adapter is None:
            log.warning("reply for unattached port %s stored only", port["id"])
            return
        adapter.submit(record.get("adapter_job_id") or record["id"], record["reply"])

    def deliver_fail(self, port: dict, record: dict) -> None:
        adapter = self.adapters.get(port["id"])
        if adapter is None:
            return
        adapter.fail(record.get("adapter_job_id") or record["id"], record.get("error") or "failed")

    def inject_mock(self, port_id: str, prompt: str, job_id: str = "demo-1") -> dict:
        adapter = self.attach(port_id)
        if not hasattr(adapter, "inject"):
            raise RuntimeError("port %s is not a mock adapter" % port_id)
        return adapter.inject(prompt, job_id=job_id)
