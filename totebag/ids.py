"""Prefixed IDs, `{prefix}_{15 url-safe chars}` scheme."""

import secrets
import string

_ALPHABET = string.ascii_lowercase + string.digits


def generate_id(prefix: str, length: int = 15) -> str:
    body = "".join(secrets.choice(_ALPHABET) for _ in range(length))
    return f"{prefix}_{body}"
