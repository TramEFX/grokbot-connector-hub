"""Port tokens and admin tokens. Constant-time compare."""

from __future__ import annotations

import hashlib
import hmac
import secrets


PORT_PREFIX = "gch_"
ADMIN_PREFIX = "gcha_"


def new_port_token() -> str:
    return PORT_PREFIX + secrets.token_urlsafe(24)


def new_admin_token() -> str:
    return ADMIN_PREFIX + secrets.token_urlsafe(24)


def equal(left: str, right: str) -> bool:
    a = (left or "").encode("utf-8")
    b = (right or "").encode("utf-8")
    if not a or not b:
        return False
    digest = lambda s: hashlib.sha256(s).digest()
    return hmac.compare_digest(digest(a), digest(b)) and len(a) == len(b)


def bearer_from_header(value: str) -> str:
    raw = (value or "").strip()
    if raw.lower().startswith("authorization:"):
        raw = raw.split(":", 1)[1].strip()
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return raw
