import time
from typing import Any

import httpx

from app.config import WEBHOOK_SECRET
from app.security import sign_payload


def build_signed_webhook(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    signature = sign_payload(payload, WEBHOOK_SECRET)
    headers = {
        "X-Platform-Signature": signature,
        "X-Platform-Timestamp": str(int(time.time())),
        "Content-Type": "application/json",
    }
    return payload, headers


def deliver_signed_webhook(webhook_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    signed_payload, headers = build_signed_webhook(payload)

    try:
        response = httpx.post(webhook_url, json=signed_payload, headers=headers, timeout=5.0)
        return {
            "webhook_url": webhook_url,
            "status_code": response.status_code,
            "success": response.is_success,
        }
    except Exception as exc:  # pragma: no cover - network call depends on external services
        return {
            "webhook_url": webhook_url,
            "status_code": 0,
            "success": False,
            "error": str(exc),
        }
