import pytest
from engine import infer_fields


def test_clean_consistent_format():
    lines = [
        "2023-01-01T00:00:00Z 192.168.1.1 INFO hello",
        "2023-01-01T00:00:01Z 192.168.1.2 WARN world",
        "2023-01-01T00:00:02Z 192.168.1.3 ERROR foo",
    ]
    result = infer_fields(lines)
    assert result["confidence"] > 0.6
    assert result["delimiter_used"] == " "
    assert result["proposed_fields"]["timestamp"] == "2023-01-01T00:00:02Z"
    assert result["proposed_fields"]["ip_address"] == "192.168.1.3"
    assert result["proposed_fields"]["level"] == "ERROR"


def test_inconsistent_set():
    lines = [
        "2023-01-01T00:00:00Z hello",
        "2023-01-01T00:00:01Z world",
        "INFO foo",
    ]
    result = infer_fields(lines)
    assert result["confidence"] == 0.5
    assert result["delimiter_used"] == " "


def test_key_value_format():
    lines = [
        "timestamp=2023-01-01T00:00:00Z level=INFO msg=hello",
        "timestamp=2023-01-01T00:00:01Z level=WARN msg=world",
        "timestamp=2023-01-01T00:00:02Z level=ERROR msg=crash",
    ]
    result = infer_fields(lines)
    assert result["delimiter_used"] == " "
    assert "timestamp" in result["proposed_fields"]
    assert "level" in result["proposed_fields"]
    assert "msg" in result["proposed_fields"]
    assert result["proposed_fields"]["timestamp"] == "2023-01-01T00:00:02Z"
    assert result["proposed_fields"]["level"] == "ERROR"
    assert result["proposed_fields"]["msg"] == "crash"

def test_pipe_delimited_no_spaces():
    lines = [
        "2026-09-04T10:22:01Z|WARN|auth-svc|user=42|action=login_fail",
        "2026-09-04T10:22:05Z|INFO|auth-svc|user=17|action=login_ok",
        "2026-09-04T10:22:09Z|ERROR|auth-svc|user=8|action=login_fail",
    ]
    result = infer_fields(lines)
    assert result["delimiter_used"] == "|"
    assert result["proposed_fields"]["timestamp"] == "2026-09-04T10:22:09Z"
    assert result["proposed_fields"]["level"] == "ERROR"
    assert result["proposed_fields"]["action"] == "login_fail"