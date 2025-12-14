from fastapi import FastAPI

app = FastAPI()

from routers import auth, logs, fixes, status

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(logs.router, prefix="/logs", tags=["logs"], include_in_schema=False)
app.include_router(fixes.router, prefix="/fixes", tags=["fixes"])
app.include_router(status.router, prefix="/status", tags=["status"])

@app.get("/")
def read_root():
    return {"Hello": "World"}