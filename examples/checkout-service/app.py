import os
import time
import uuid
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Mock Checkout Service", version="1.0.0")

DAA_LOGS_URL = os.environ.get("DAA_LOGS_URL", "http://localhost:8000/logs/")
PAYMENT_SERVICE_URL = os.environ.get("PAYMENT_SERVICE_URL", "http://localhost:8002/pay")
REDIS_HOST = os.environ.get("REDIS_HOST", "redis-master")
REDIS_PORT = os.environ.get("REDIS_PORT", "6379")

class CheckoutRequest(BaseModel):
    user_id: str
    cart_total: float
    currency: str = "USD"

def report_error_to_daa(exception_type: str, content: str, trace_id: str):
    """Sends structured telemetry error logs to DAA Autonomous SRE Platform."""
    payload = {
        "app_name": "checkout-service",
        "content": content,
        "exception_type": exception_type,
        "trace_id": trace_id,
        "correlation_id": str(uuid.uuid4())
    }
    try:
        res = requests.post(DAA_LOGS_URL, json=payload, timeout=2.0)
        print(f"[Telemetry] Reported to DAA -> Status: {res.status_code}, Response: {res.json()}")
        return res.json()
    except Exception as e:
        print(f"[Telemetry Error] Could not connect to DAA backend: {e}")
        return None

@app.post("/checkout")
def process_checkout(req: CheckoutRequest):
    trace_id = f"trace-{uuid.uuid4().hex[:12]}"
    print(f"[{trace_id}] Starting checkout for user {req.user_id} (${req.cart_total})")
    
    # 1. Simulate Redis connection check (Intentionally fails to demonstrate outage)
    if req.cart_total > 1000.0 or "fail_redis" in req.user_id:
        err_msg = f"RedisTimeoutError: Connection timed out connecting to {REDIS_HOST}:{REDIS_PORT} after 5000ms. Pool exhausted."
        print(f"[{trace_id}] ERROR: {err_msg}")
        report_error_to_daa("RedisTimeoutError", err_msg, trace_id)
        raise HTTPException(status_code=504, detail="Cache gateway timeout")

    # 2. Simulate call to downstream Payment Service
    try:
        pay_res = requests.post(PAYMENT_SERVICE_URL, json={"amount": req.cart_total, "trace_id": trace_id}, timeout=3.0)
        if pay_res.status_code != 200:
            err_msg = f"PaymentGatewayError: Downstream payment service returned {pay_res.status_code}"
            report_error_to_daa("PaymentGatewayError", err_msg, trace_id)
            raise HTTPException(status_code=502, detail=pay_res.text)
    except requests.exceptions.RequestException as e:
        err_msg = f"DownstreamConnectionError: Failed to reach payment service at {PAYMENT_SERVICE_URL}: {str(e)}"
        report_error_to_daa("DownstreamConnectionError", err_msg, trace_id)
        raise HTTPException(status_code=503, detail="Payment service unavailable")

    return {"status": "SUCCESS", "transaction_id": f"txn_{uuid.uuid4().hex[:8]}", "trace_id": trace_id}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "checkout-service"}
