"""Agensis Connector adapter.

Speaks the published Connector tools on POST /backend/mcp:

    whoami, claim_job, submit_job_result, fail_job

This is an independent client of that public contract (see jasonkneen/agensis
server/MCP.md). It is not a fork and does not include Agensis source.

Presence is stamped by claim_job even on an empty poll. The hub owns that
loop so the Grok Bot can sleep. Claimed jobs are budgeted under the
documented ~10 minute idle reap.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from .. import mailbox, ports

log = logging.getLogger("gch.agensis")

USER_AGENT = "grokbot-connector-hub/0.1"
BACKOFF_START = 2.0
BACKOFF_MAX = 60.0


class McpError(RuntimeError):
    pass


class AgensisAdapter:
    name = "agensis"

    def __init__(self, port: dict, data_dir: Path, on_job):
        self.port = port
        self.data_dir = data_dir
        self.on_job = on_job
        cfg = port.get("adapter_config") or {}
        self.mcp_url = (cfg.get("mcp_url") or "").rstrip("/")
        self.token = cfg.get("token") or ""
        self.poll_seconds = float(cfg.get("poll_seconds") or 3)
        self.job_budget = float(cfg.get("job_budget_seconds") or 480)
        self.http_timeout = float(cfg.get("http_timeout") or 60)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.mcp_url or not self.token.startswith("aga_"):
            raise RuntimeError(
                "port %s needs adapter_config.mcp_url and adapter_config.token (aga_)"
                % self.port["id"]
            )
        me = self.call("whoami")
        log.info(
            "agensis connected port=%s handle=@%s workspace=%s",
            self.port["id"],
            me.get("handle"),
            me.get("workspaceId"),
        )
        ports.update(
            self.port["id"],
            {"presence": "present", "last_seen_at": _now()},
            self.data_dir,
        )
        self._thread = threading.Thread(target=self._heartbeat, name="agensis-" + self.port["id"], daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def call(self, tool: str, arguments: dict | None = None) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments or {}},
        }
        req = urllib.request.Request(
            self.mcp_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.http_timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            raise McpError("HTTP %s %s" % (err.code, err.reason)) from err
        if body.get("error"):
            raise McpError(body["error"].get("message", "unknown MCP error"))
        result = body.get("result") or {}
        for part in result.get("content") or []:
            if part.get("type") == "text":
                try:
                    return json.loads(part["text"])
                except json.JSONDecodeError:
                    return {"text": part["text"]}
        return result

    def submit(self, job_id: str, reply: str) -> None:
        last_err = None
        for attempt in range(1, 4):
            try:
                self.call("submit_job_result", {"job_id": job_id, "response": reply})
                return
            except Exception as err:  # noqa: BLE001
                last_err = err
                log.warning("submit attempt %s failed for %s: %s", attempt, job_id, err)
                time.sleep(attempt)
        raise McpError("submit_job_result failed: %s" % last_err)

    def fail(self, job_id: str, error: str) -> None:
        try:
            self.call("fail_job", {"job_id": job_id, "error": (error or "")[:500]})
        except Exception as err:  # noqa: BLE001
            log.exception("fail_job also failed for %s: %s", job_id, err)

    def _heartbeat(self) -> None:
        backoff = BACKOFF_START
        while not self._stop.is_set():
            try:
                raw = self.call("claim_job") or {}
                job = raw.get("job")
                ports.update(
                    self.port["id"],
                    {"presence": "present", "last_seen_at": _now()},
                    self.data_dir,
                )
                backoff = BACKOFF_START
                if job:
                    self._ingest(job)
                    continue
            except (urllib.error.URLError, McpError) as err:
                log.warning("agensis poll port=%s: %s", self.port["id"], err)
                ports.update(self.port["id"], {"presence": "degraded"}, self.data_dir)
                self._stop.wait(backoff)
                backoff = min(backoff * 2, BACKOFF_MAX)
                continue
            except Exception:  # noqa: BLE001
                log.exception("unexpected agensis error port=%s", self.port["id"])
                self._stop.wait(backoff)
                backoff = min(backoff * 2, BACKOFF_MAX)
                continue
            self._stop.wait(self.poll_seconds)

    def _ingest(self, job: dict) -> None:
        raw_id = job.get("id") or job.get("jobId") or job.get("job_id")
        try:
            job_id = mailbox.sanitize_job_id(str(raw_id))
        except mailbox.MailboxError:
            log.error("refusing unsanitized job id %r", raw_id)
            if raw_id:
                self.fail(str(raw_id), "hub rejected unsafe job id")
            return
        record = mailbox.put(
            self.port["id"],
            {
                "id": job_id,
                "adapter_job_id": job_id,
                "prompt": job.get("prompt") or "",
                "session_id": job.get("session_id") or job.get("sessionId"),
                "metadata": job.get("metadata") or {},
                "budget_seconds": self.job_budget,
            },
            self.data_dir,
        )
        log.info("claimed %s for %s (%d chars)", job_id, self.port["id"], len(record["prompt"]))
        self.on_job(record)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
