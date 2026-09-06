import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_admin
from config import (
    CLICKHOUSE_DATABASE,
    CLICKHOUSE_PASSWORD,
    CLICKHOUSE_URL,
    CLICKHOUSE_USER,
)

router = APIRouter(prefix="/api", dependencies=[Depends(get_current_admin)])


def _escape(value: str) -> str:
    return value.replace("'", "\\'")


def _ch_query(query: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
    if not CLICKHOUSE_URL:
        raise HTTPException(status_code=503, detail="ClickHouse not configured")

    url = CLICKHOUSE_URL.rstrip("/") + "/"
    query_params: dict[str, str] = {
        "database": CLICKHOUSE_DATABASE,
        "default_format": "JSONEachRow",
    }
    if params:
        query_params.update(params)
    if CLICKHOUSE_USER:
        query_params["user"] = CLICKHOUSE_USER
    if CLICKHOUSE_PASSWORD:
        query_params["password"] = CLICKHOUSE_PASSWORD

    query_string = "&".join(
        f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in query_params.items()
    )
    full_url = f"{url}?{query_string}"

    req = urllib.request.Request(
        full_url,
        data=query.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "text/plain"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8").strip()
            if not body:
                return []
            return [json.loads(line) for line in body.splitlines()]
    except urllib.error.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"ClickHouse error: {exc.code} {exc.reason}",
        )
    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"ClickHouse unavailable: {exc.reason}",
        )


@router.get("/logs/recent")
def logs_recent(
    limit: int = Query(50, ge=1, le=1000),
) -> list[dict[str, Any]]:
    query = (
        f"SELECT * FROM parsed_logs ORDER BY ingested_at DESC LIMIT {limit}"
    )
    return _ch_query(query)


@router.get("/review-queue")
def review_queue(
    status: str = Query("pending"),
) -> list[dict[str, Any]]:
    safe_status = _escape(status)
    query = (
        f"SELECT * FROM review_queue WHERE status = '{safe_status}' ORDER BY ingested_at DESC"
    )
    return _ch_query(query)


@router.post("/review-queue/{event_id}/approve")
def review_approve(event_id: str) -> dict[str, str]:
    safe_id = _escape(event_id)
    rows = _ch_query(
        f"SELECT * FROM review_queue WHERE event_id = '{safe_id}' LIMIT 1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Event not found in review queue")

    row = rows[0]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    json_row = json.dumps(
        {
            "event_id": row["event_id"],
            "source": row["source"],
            "raw_line": row["raw_line"],
            "event_timestamp": row["event_timestamp"],
            "format": "inferred_approved",
            "fields_json": row["fields_json"],
            "metadata_json": row["metadata_json"],
            "ingested_at": now,
        },
        ensure_ascii=False,
    )

    insert_query = "INSERT INTO parsed_logs FORMAT JSONEachRow"

    if not CLICKHOUSE_URL:
        raise HTTPException(status_code=503, detail="ClickHouse not configured")

    url = CLICKHOUSE_URL.rstrip("/") + "/"
    query_params: dict[str, str] = {"query": insert_query, "default_format": "JSONEachRow"}
    if CLICKHOUSE_USER:
        query_params["user"] = CLICKHOUSE_USER
    if CLICKHOUSE_PASSWORD:
        query_params["password"] = CLICKHOUSE_PASSWORD

    query_string = "&".join(
        f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in query_params.items()
    )
    full_url = f"{url}?{query_string}"

    req = urllib.request.Request(
        full_url,
        data=json_row.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except urllib.error.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"ClickHouse error: {exc.code} {exc.reason}",
        )
    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"ClickHouse unavailable: {exc.reason}",
        )

    update_query = (
        f"ALTER TABLE review_queue UPDATE status = 'approved' WHERE event_id = '{safe_id}'"
    )
    _ch_query(update_query)
    return {"status": "approved"}


@router.post("/review-queue/{event_id}/reject")
def review_reject(event_id: str) -> dict[str, str]:
    safe_id = _escape(event_id)
    rows = _ch_query(
        f"SELECT * FROM review_queue WHERE event_id = '{safe_id}' LIMIT 1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Event not found in review queue")

    update_query = (
        f"ALTER TABLE review_queue UPDATE status = 'rejected' WHERE event_id = '{safe_id}'"
    )
    _ch_query(update_query)
    return {"status": "rejected"}


@router.get("/stats/throughput")
def stats_throughput() -> dict[str, Any]:
    query = (
        "SELECT count() AS count FROM parsed_logs WHERE ingested_at >= now() - INTERVAL 10 SECOND"
    )
    rows = _ch_query(query)
    count = rows[0].get("count", 0) if rows else 0
    return {"events_last_10s": count}
