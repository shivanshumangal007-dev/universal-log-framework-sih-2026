from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from kafka_worker import get_stats, run_kafka_worker
import threading

from pydantic import BaseModel

from auth import verify_password, create_access_token, get_current_admin
from config import ADMIN_USERNAME, ADMIN_PASSWORD_HASH, DASHBOARD_ORIGIN
from gateway import router as gateway_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[DASHBOARD_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

worker_stop_event = threading.Event()
worker_thread: threading.Thread | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


class LoginPayload(BaseModel):
    username: str
    password: str


@app.post("/auth/login")
def login(payload: LoginPayload) -> dict:
    if not ADMIN_USERNAME or not ADMIN_PASSWORD_HASH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin credentials not configured",
        )
    if payload.username != ADMIN_USERNAME or not verify_password(
        payload.password, ADMIN_PASSWORD_HASH
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token({"sub": ADMIN_USERNAME})
    return {"access_token": token, "token_type": "bearer"}


@app.on_event("startup")
def start_kafka_worker() -> None:
    global worker_thread
    worker_stop_event.clear()
    worker_thread = threading.Thread(
        target=run_kafka_worker,
        args=(worker_stop_event,),
        name="kafka-inference-worker",
        daemon=True,
    )
    worker_thread.start()


@app.on_event("shutdown")
def stop_kafka_worker() -> None:
    worker_stop_event.set()
    if worker_thread is not None:
        worker_thread.join(timeout=2)


@app.get("/inference/stats")
def inference_stats() -> dict:
    return get_stats()


app.include_router(gateway_router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
