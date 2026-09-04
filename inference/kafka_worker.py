import json
import logging
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

from config import (
    KAFKA_BROKERS,
    KAFKA_GROUP_ID,
    KAFKA_INFERRED_TOPIC,
    KAFKA_UNKNOWN_TOPIC,
)
from engine import infer_fields


WINDOW_LIMIT = 50
WINDOW_DURATION = timedelta(minutes=5)
KAFKA_RETRY_SECONDS = 5
KAFKA_BOOTSTRAP_TIMEOUT_MS = 5000
logger = logging.getLogger(__name__)


@dataclass
class WindowLine:
    seen_at: datetime
    raw_line: str
    confidence: float = 0.0


_windows: dict[str, deque[WindowLine]] = defaultdict(
    lambda: deque(maxlen=WINDOW_LIMIT)
)
_windows_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _prune(window: deque[WindowLine], now: datetime) -> None:
    cutoff = now - WINDOW_DURATION
    while window and window[0].seen_at < cutoff:
        window.popleft()


def process_event(
    event: dict[str, Any],
    producer: Any,
    seen_at: datetime | None = None,
) -> dict[str, Any]:
    """Infer one event, update its source window, and publish the result."""
    source = str(event["source"])
    raw_line = str(event["raw_line"])
    observed_at = seen_at or _now()

    with _windows_lock:
        window = _windows[source]
        _prune(window, observed_at)
        window.append(WindowLine(observed_at, raw_line))
        inference = infer_fields([item.raw_line for item in window])
        window[-1].confidence = inference["confidence"]

    payload = {
        "source": source,
        "raw_line": raw_line,
        "proposed_fields": inference["proposed_fields"],
        "confidence": inference["confidence"],
        "delimiter_used": inference["delimiter_used"],
        "inferred_at": _isoformat(observed_at),
    }
    producer.send(
        KAFKA_INFERRED_TOPIC,
        key=source.encode("utf-8"),
        value=json.dumps(payload).encode("utf-8"),
    ).get(timeout=10)
    return payload


def get_stats(now: datetime | None = None) -> dict[str, dict[str, float | int]]:
    """Return recent line counts and average confidence grouped by source."""
    current_time = now or _now()
    with _windows_lock:
        stats = {}
        for source, window in _windows.items():
            _prune(window, current_time)
            if window:
                stats[source] = {
                    "line_count": len(window),
                    "average_confidence": round(
                        sum(item.confidence for item in window) / len(window), 2
                    ),
                }
        return stats


def run_kafka_worker(
    stop_event: threading.Event | None = None,
    consumer: Any | None = None,
    producer: Any | None = None,
) -> None:
    """Consume unknown logs until stop_event is set and publish inferences."""
    stop_event = stop_event or threading.Event()
    injected_clients = consumer is not None or producer is not None
    brokers = [broker.strip() for broker in KAFKA_BROKERS.split(",") if broker.strip()]

    while not stop_event.is_set():
        active_consumer = consumer
        active_producer = producer
        owns_clients = not injected_clients
        try:
            if active_consumer is None:
                active_consumer = KafkaConsumer(
                    KAFKA_UNKNOWN_TOPIC,
                    bootstrap_servers=brokers,
                    group_id=KAFKA_GROUP_ID,
                    enable_auto_commit=True,
                    request_timeout_ms=KAFKA_BOOTSTRAP_TIMEOUT_MS,
                )
            if active_producer is None:
                active_producer = KafkaProducer(
                    bootstrap_servers=brokers,
                    request_timeout_ms=KAFKA_BOOTSTRAP_TIMEOUT_MS,
                )

            while not stop_event.is_set():
                records = active_consumer.poll(timeout_ms=1000)
                for messages in records.values():
                    for message in messages:
                        event = json.loads(message.value.decode("utf-8"))
                        process_event(event, active_producer)
            break
        except (KafkaError, OSError, ValueError, json.JSONDecodeError) as error:
            logger.warning(
                "Kafka unavailable or worker message failed: %s; retrying in %ss",
                error,
                KAFKA_RETRY_SECONDS,
            )
            if injected_clients:
                break
            stop_event.wait(KAFKA_RETRY_SECONDS)
        finally:
            if owns_clients:
                if active_consumer is not None:
                    active_consumer.close()
                if active_producer is not None:
                    active_producer.close()


def clear_state() -> None:
    """Clear in-memory state; useful for isolated tests and local restarts."""
    with _windows_lock:
        _windows.clear()