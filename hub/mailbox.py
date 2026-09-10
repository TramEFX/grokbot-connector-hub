"""Per-port job mailbox. Source of truth for a turn. Webhook is only a doorbell."""

from __future__ import annotations

import re
import time
from pathlib import Path

from .store import default_data_dir, ensure_dir, read_json, write_json

SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class MailboxError(ValueError):
    pass


def sanitize_job_id(job_id: str) -> str:
    value = str(job_id or "").strip()
    if not SAFE_ID.match(value):
        raise MailboxError("unsafe or empty job id")
    return value


def _box(port_id: str, data_dir: Path | None = None) -> Path:
    return ensure_dir((data_dir or default_data_dir()) / "mailbox" / port_id)


def _path(port_id: str, job_id: str, data_dir: Path | None = None) -> Path:
    return _box(port_id, data_dir) / (sanitize_job_id(job_id) + ".json")


def put(port_id: str, job: dict, data_dir: Path | None = None) -> dict:
    job_id = sanitize_job_id(job.get("id") or job.get("job_id") or "")
    now = time.time()
    record = {
        "id": job_id,
        "port_id": port_id,
        "prompt": job.get("prompt") or "",
        "session_id": job.get("session_id"),
        "metadata": job.get("metadata") or {},
        "status": "open",
        "created_at": now,
        "deadline_at": job.get("deadline_at") or (now + float(job.get("budget_seconds") or 480)),
        "reply": None,
        "error": None,
        "adapter_job_id": job.get("adapter_job_id") or job_id,
    }
    write_json(_path(port_id, job_id, data_dir), record)
    return record


def get(port_id: str, job_id: str, data_dir: Path | None = None) -> dict:
    path = _path(port_id, job_id, data_dir)
    if not path.exists():
        raise MailboxError("unknown job: %s" % job_id)
    return read_json(path, {})


def list_open(port_id: str, data_dir: Path | None = None) -> list:
    box = _box(port_id, data_dir)
    rows = []
    for path in sorted(box.glob("*.json")):
        row = read_json(path, {})
        if row.get("status") == "open":
            rows.append(row)
    rows.sort(key=lambda r: r.get("created_at") or 0)
    return rows


def reply(port_id: str, job_id: str, text: str, data_dir: Path | None = None) -> dict:
    record = get(port_id, job_id, data_dir)
    if record.get("status") != "open":
        raise MailboxError("job %s is %s" % (job_id, record.get("status")))
    body = (text or "").strip()
    if not body:
        raise MailboxError("empty reply")
    record["status"] = "replied"
    record["reply"] = body
    record["answered_at"] = time.time()
    write_json(_path(port_id, job_id, data_dir), record)
    return record


def fail(port_id: str, job_id: str, error: str, data_dir: Path | None = None) -> dict:
    record = get(port_id, job_id, data_dir)
    if record.get("status") != "open":
        raise MailboxError("job %s is %s" % (job_id, record.get("status")))
    record["status"] = "failed"
    record["error"] = (error or "failed")[:500]
    record["answered_at"] = time.time()
    write_json(_path(port_id, job_id, data_dir), record)
    return record


def expire_open(port_id: str, data_dir: Path | None = None) -> list:
    expired = []
    now = time.time()
    for row in list_open(port_id, data_dir):
        if float(row.get("deadline_at") or 0) <= now:
            expired.append(fail(port_id, row["id"], "deadline exceeded", data_dir))
    return expired
