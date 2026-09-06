import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

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


def _ensure_schema_table() -> None:
    """Create the learned-schema table if it doesn't exist yet.

    Cheap to call on every correction (CREATE TABLE IF NOT EXISTS) —
    avoids needing separate startup-ordering logic for this table.
    ReplacingMergeTree keyed by source + updated_at: querying with
    FINAL (or ORDER BY updated_at DESC LIMIT 1) always gets the most
    recent human-confirmed schema for that source.
    """
    _ch_query(
        "CREATE TABLE IF NOT EXISTS source_schemas ("
        "source String, "
        "delimiter_used String, "
        "field_mapping_json String, "
        "updated_at DateTime"
        ") ENGINE = ReplacingMergeTree(updated_at) ORDER BY source"
    )


def _learn_schema(source: str, delimiter_used: str, field_names_ordered: list[str]) -> None:
    """Remember a human-corrected field mapping for this source.

    field_names_ordered is positional — index 0 is whatever field name
    the admin gave the first delimiter-split token, etc. — so future
    raw lines from the same source can be split the same way and get
    the same names applied, without re-running the generic guesser.
    """
    _ensure_schema_table()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    row = json.dumps(
        {
            "source": source,
            "delimiter_used": delimiter_used,
            "field_mapping_json": json.dumps(field_names_ordered, ensure_ascii=False),
            "updated_at": now,
        },
        ensure_ascii=False,
    )

    if not CLICKHOUSE_URL:
        return  # fail open — learning is a bonus, never block the approve flow

    url = CLICKHOUSE_URL.rstrip("/") + "/"
    query_params: dict[str, str] = {
        "query": "INSERT INTO source_schemas FORMAT JSONEachRow",
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
    full_url = f"{url}?{query_string}"
    req = urllib.request.Request(
        full_url,
        data=row.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except (urllib.error.HTTPError, urllib.error.URLError):
        pass  # fail open — a failed learn-write should never break approve itself


class CorrectionPayload(BaseModel):
    fields_json: dict[str, Any]


@router.post("/review-queue/{event_id}/approve")
def review_approve(event_id: str, payload: CorrectionPayload | None = None) -> dict[str, str]:
    """Approve a review-queue entry, optionally with corrected field values.

    - Admin just clicks Approve, no edits: payload is None, we reuse the
      engine's original fields_json as-is, tagged inferred_approved.
    - Admin edited the proposed fields before approving: payload carries
      the corrected values instead, tagged inferred_corrected so there's
      an honest record a human fixed it rather than trusting the engine's
      raw guess.
    Either way, exactly one row lands in parsed_logs and review_queue's
    status reflects which path was taken.
    """
    safe_id = _escape(event_id)
    rows = _ch_query(
        f"SELECT * FROM review_queue WHERE event_id = '{safe_id}' LIMIT 1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Event not found in review queue")

    row = rows[0]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    if payload is not None and payload.fields_json:
        fields_json_value = json.dumps(payload.fields_json, ensure_ascii=False)
        format_tag = "inferred_corrected"
        new_status = "corrected"

        # Learn from this correction: remember the field names the admin
        # gave, in order, keyed by source — so the NEXT line from this
        # same source can skip the generic guess and use this directly.
        try:
            original_metadata = json.loads(row.get("metadata_json") or "{}")
            delimiter_used = original_metadata.get("delimiter_used", " ")
            field_names_ordered = list(payload.fields_json.keys())
            _learn_schema(row["source"], delimiter_used, field_names_ordered)
        except Exception:
            pass  # learning is a bonus on top of approve — never let it block the approve itself
    else:
        fields_json_value = row["fields_json"]
        format_tag = "inferred_approved"
        new_status = "approved"

    json_row = json.dumps(
        {
            "event_id": row["event_id"],
            "source": row["source"],
            "raw_line": row["raw_line"],
            "event_timestamp": row["event_timestamp"],
            "format": format_tag,
            "fields_json": fields_json_value,
            "metadata_json": row["metadata_json"],
            "ingested_at": now,
        },
        ensure_ascii=False,
    )

    insert_query = "INSERT INTO parsed_logs FORMAT JSONEachRow"

    if not CLICKHOUSE_URL:
        raise HTTPException(status_code=503, detail="ClickHouse not configured")

    url = CLICKHOUSE_URL.rstrip("/") + "/"
    query_params: dict[str, str] = {
        "query": insert_query,
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
        f"ALTER TABLE review_queue UPDATE status = '{new_status}' WHERE event_id = '{safe_id}'"
    )
    _ch_query(update_query)
    return {"status": new_status}


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