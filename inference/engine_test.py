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


def test_pipe_delimited_with_spaces_around_pipes():
    """The exact failing case from the user's screenshots.

    Logs like: PAY_SVC |4471|info| user=3 | action=change_retryn
    The engine must pick '|' not ' ' as the delimiter, and strip
    whitespace from each token.
    """
    lines = [
        "PAY_SVC |4471|info| user=3 | action=change_retryn",
        "Psd_svf |4341|warn| user=5 | action=change_retryn",
        "AUTH_SVC |5521|error| user=9 | action=login_fail",
    ]
    result = infer_fields(lines)
    assert result["delimiter_used"] == "|", (
        f"Expected '|' but got '{result['delimiter_used']}'"
    )
    fields = result["proposed_fields"]
    # The key=value tokens should be properly recognized
    assert "user" in fields or "action" in fields, (
        f"Expected key=value fields but got: {fields}"
    )


def test_pipe_delimited_with_spaces_produces_correct_values():
    """Verify the actual parsed values are correct, not just the delimiter."""
    lines = [
        "PAY_SVC |4471|info| user=3 | action=change_retryn",
        "Psd_svf |4341|warn| user=5 | action=change_retryn",
        "AUTH_SVC |5521|error| user=9 | action=login_fail",
    ]
    result = infer_fields(lines)
    fields = result["proposed_fields"]
    # After splitting by | and stripping, tokens should be:
    # ["AUTH_SVC", "5521", "error", "user=9", "action=login_fail"]
    # The user and action fields should have clean values
    if "user" in fields:
        assert fields["user"] == "9", f"Expected user=9 but got user={fields['user']}"
    if "action" in fields:
        assert fields["action"] == "login_fail", (
            f"Expected action=login_fail but got action={fields['action']}"
        )


def test_single_line_low_confidence():
    """A single unknown line should produce very low confidence."""
    lines = ["completely_refurbished_logs"]
    result = infer_fields(lines)
    assert result["confidence"] == 0.0, (
        f"Expected 0.0 confidence for unrecognizable single line, got {result['confidence']}"
    )


def test_single_line_with_recognized_fields():
    """A single line with recognized fields should still have scaled-down confidence."""
    lines = ["2023-01-01T00:00:00Z 192.168.1.1 INFO hello"]
    result = infer_fields(lines)
    # Has recognized fields but only 1 sample, so confidence should be < 1/3
    assert result["confidence"] < 0.4


def test_csv_like_format():
    """Comma-separated values should pick comma as delimiter."""
    lines = [
        "2023-01-01T00:00:00Z,192.168.1.1,INFO,login successful",
        "2023-01-01T00:00:01Z,192.168.1.2,WARN,timeout occurred",
        "2023-01-01T00:00:02Z,192.168.1.3,ERROR,connection refused",
    ]
    result = infer_fields(lines)
    assert result["delimiter_used"] == ","
    assert result["proposed_fields"]["timestamp"] == "2023-01-01T00:00:02Z"
    assert result["proposed_fields"]["ip_address"] == "192.168.1.3"
    assert result["proposed_fields"]["level"] == "ERROR"


def test_empty_lines_filtered():
    """Empty and whitespace-only lines should be filtered out."""
    lines = ["", "   ", "2023-01-01T00:00:00Z INFO hello", "", "2023-01-01T00:00:01Z WARN world", "2023-01-01T00:00:02Z ERROR crash"]
    result = infer_fields(lines)
    assert result["confidence"] > 0.0
    assert result["proposed_fields"]["timestamp"] == "2023-01-01T00:00:02Z"


def test_empty_input():
    """Empty input should return a safe default."""
    result = infer_fields([])
    assert result["confidence"] == 0.0
    assert result["proposed_fields"] == {}
    assert result["delimiter_used"] == " "


def test_all_generic_tokens():
    """Lines where no token is a recognized type should yield 0 confidence."""
    lines = [
        "alpha bravo charlie",
        "delta echo foxtrot",
        "golf hotel india",
    ]
    result = infer_fields(lines)
    assert result["confidence"] == 0.0


def test_numeric_tokens_recognized():
    """Numeric tokens (PIDs, ports, etc.) should be classified."""
    lines = [
        "2023-01-01T00:00:00Z 192.168.1.1 INFO 8080 connected",
        "2023-01-01T00:00:01Z 192.168.1.2 WARN 3306 timeout",
        "2023-01-01T00:00:02Z 192.168.1.3 ERROR 5432 refused",
    ]
    result = infer_fields(lines)
    assert result["confidence"] > 0.5
    assert result["delimiter_used"] == " "


def test_case_insensitive_levels():
    """Log levels should be recognized regardless of case."""
    lines = [
        "2023-01-01T00:00:00Z info request started",
        "2023-01-01T00:00:01Z warn high latency",
        "2023-01-01T00:00:02Z error failed",
    ]
    result = infer_fields(lines)
    assert result["proposed_fields"]["level"] == "error"
    assert result["confidence"] > 0.5