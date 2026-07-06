import os
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Mock Payment Service", version="1.0.0")

class PaymentRequest(BaseModel):
    amount: float
    trace_id: str

@app.post("/pay")
def process_payment(req: PaymentRequest):
    print(f"[{req.trace_id}] Processing payment of ${req.amount}")
    if req.amount > 5000.0:
        raise HTTPException(status_code=402, detail="StripeChargeFailed: Card declined or insufficient funds.")
    return {"status": "PAID", "gateway_ref": f"ch_{uuid.uuid4().hex[:10]}"}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "payment-service"}
