"""On-disk store: ports.json + mailbox files under a data root."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path


_lock = threading.RLock()


def default_data_dir() -> Path:
    override = os.environ.get("GCH_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".grokbot-connector-hub"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def read_json(path: Path, default):
    with _lock:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".part")
    text = json.dumps(payload, indent=2, sort_keys=True)
    with _lock:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
