"""Best-effort webhook wake. Mailbox is the source of truth."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from .auth import bearer_from_header

log = logging.getLogger("gch.doorbell")
USER_AGENT = "grokbot-connector-hub/0.1"


def ring(url: str, auth_header: str, payload: dict, timeout: float = 10.0) -> bool:
    if not url:
        return False
    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    token = bearer_from_header(auth_header)
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            log.info("doorbell ok job=%s", payload.get("job_id"))
            return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as err:
        log.warning("doorbell failed job=%s (%s) — inbox is still the source of truth", payload.get("job_id"), err)
        return False
