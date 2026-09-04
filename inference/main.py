from fastapi import FastAPI
import uvicorn

from kafka_worker import get_stats, run_kafka_worker
import threading

app = FastAPI()
worker_stop_event = threading.Event()
worker_thread: threading.Thread | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
