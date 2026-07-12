import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


async def send_outbound_webhook(payload: dict):
    url = os.environ.get("DAA_OUTBOUND_WEBHOOK_URL")
    if not url:
        logger.info(
            "DAA_OUTBOUND_WEBHOOK_URL not configured. Skipping outbound notification."
        )
        return

    secret = os.environ.get("DAA_OUTBOUND_WEBHOOK_SECRET")

    # Enrich payload with standard properties if not present
    if "event" not in payload:
        payload["event"] = "daa.investigation.completed"
    if "timestamp" not in payload:
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()

    data = json.dumps(payload)
    headers = {"Content-Type": "application/json"}

    if secret:
        signature = hmac.new(
            secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        headers["X-DAA-Signature"] = signature

    logger.info(
        f"Dispatching outbound webhook to {url} with signature header: {headers.get('X-DAA-Signature') is not None}"
    )
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, content=data, timeout=10.0)
            logger.info(f"Outbound webhook response: {resp.status_code}")
    except Exception as e:
        logger.error(f"Failed to dispatch outbound webhook: {e}")
