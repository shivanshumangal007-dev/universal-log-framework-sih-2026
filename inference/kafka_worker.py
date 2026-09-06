import json
import logging
import threading
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

from config import (
    CLICKHOUSE_DATABASE,
    CLICKHOUSE_PASSWORD,
    CLICKHOUSE_URL,
    CLICKHOUSE_USER,
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
CLICKHOUSE_LOOKUP_TIMEOUT_S = 3
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


def _lookup_learned_schema(source: str) -> tuple[list[str], str] | None:
    """Check if a human has already corrected this exact source before.

    Returns (ordered_field_names, delimiter_used) if a learned schema
    exists, else None. This is a pure bonus lookup — ANY failure here
    (ClickHouse unreachable, table doesn't exist yet, bad response)
    must fall back to None so the caller uses the generic inference
    engine instead. A broken learning feature must never break the
    baseline pipeline that already works.
    """
    if not CLICKHOUSE_URL:
        return None
    try:
        safe_source = source.replace("'", "\\'")
        query = (
            "SELECT field_mapping_json, delimiter_used FROM source_schemas "
            f"FINAL WHERE source = '{safe_source}' "
            "ORDER BY updated_at DESC LIMIT 1"
        )
        query_params: dict[str, str] = {
            "database": CLICKHOUSE_DATABASE,
            "default_format": "JSONEachRow",
        }
        if CLICKHOUSE_USER:
            query_params["user"] = CLICKHOUSE_USER
        if CLICKHOUSE_PASSWORD:
            query_params["password"] = CLICKHOUSE_PASSWORD
        query_string = "&".join(
            f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in query_params.items()
        )
        url = CLICKHOUSE_URL.rstrip("/") + "/?" + query_string
        req = urllib.request.Request(
            url,
            data=query.encode("utf-8"),
            method="POST",
            headers={"Content-Type": "text/plain"},
        )
        with urllib.request.urlopen(req, timeout=CLICKHOUSE_LOOKUP_TIMEOUT_S) as resp:
            body = resp.read().decode("utf-8").strip()
            if not body:
                return None
            row = json.loads(body.splitlines()[0])
            field_names = json.loads(row["field_mapping_json"])
            return field_names, row["delimiter_used"]
    except Exception:
        return None


def process_event(
    event: dict[str, Any],
    producer: Any,
    seen_at: datetime | None = None,
) -> dict[str, Any]:
    """Infer one event, update its source window, and publish the result."""
    source = str(event["source"])
    raw_line = str(event["raw_line"])
    observed_at = seen_at or _now()

    learned = _lookup_learned_schema(source)

    with _windows_lock:
        window = _windows[source]
        _prune(window, observed_at)
        window.append(WindowLine(observed_at, raw_line))

        if learned is not None:
            # A human already taught us this source's format — apply it
            # directly instead of running the generic guesser again.
            field_names, delimiter_used = learned
            if delimiter_used == " ":
                tokens = raw_line.split()
            else:
                tokens = [t.strip() for t in raw_line.split(delimiter_used)]
            # Filter out empty tokens (from leading/trailing delimiters)
            tokens = [t for t in tokens if t]
            proposed_fields = {}
            for i, token in enumerate(tokens):
                field_name = field_names[i] if i < len(field_names) else f"field_{i}"
                # Handle key=value tokens: if the token is "user=23"
                # and the learned field name is "user", extract just "23"
                if "=" in token:
                    k, v = token.split("=", 1)
                    if k.strip() == field_name:
                        token = v.strip()
                proposed_fields[field_name] = token
            inference = {
                "proposed_fields": proposed_fields,
                "confidence": 1.0,
                "delimiter_used": delimiter_used,
            }
        else:
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
                    auto_offset_reset="earliest",
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