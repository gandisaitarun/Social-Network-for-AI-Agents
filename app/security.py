import hashlib
import hmac
import json
import re
from typing import Any


INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "system prompt",
    "developer prompt",
    "reveal secret",
    "reveal secrets",
    "confidential key",
    "api key",
    "private key",
    "override instructions",
    "act as",
    "bypass safety",
    "delete the database",
)


def sanitize_text(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value or "").strip()
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", cleaned)
    return cleaned


class UnsafeContentError(ValueError):
    """Raised when content trips the guardrail. The API maps this to HTTP 400."""


def guardrail_check(text: str) -> str:
    normalized = sanitize_text(text).lower()
    for pattern in INJECTION_PATTERNS:
        # Whole-word match so benign text such as "exact as" does not trip "act as".
        if re.search(rf"(?<!\w){re.escape(pattern)}s?(?!\w)", normalized):
            raise UnsafeContentError("Unsafe content detected")
    return sanitize_text(text)


def sign_payload(payload: dict[str, Any], secret: str) -> str:
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), serialized, hashlib.sha256).hexdigest()
    return digest


def verify_signature(payload: dict[str, Any], signature: str, secret: str) -> bool:
    expected = sign_payload(payload, secret)
    return hmac.compare_digest(expected, signature)
