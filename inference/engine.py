import re
from collections import Counter

# Regex patterns
ISO_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$"
)
IP_RE = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)$"
)
LEVELS = {"INFO", "WARN", "ERROR", "DEBUG", "CRITICAL",
          "info", "warn", "error", "debug", "critical",
          "warning", "WARNING", "FATAL", "fatal", "TRACE", "trace"}

# Require this many samples before confidence is allowed to reach its
# full computed value; below it, confidence is scaled down linearly.
MIN_SAMPLE_SIZE = 3


def _token_type(token: str) -> str:
    """Classify a single token into a semantic type."""
    token = token.strip()
    if not token:
        return "empty"
    if ISO_TIMESTAMP_RE.match(token):
        return "timestamp"
    if IP_RE.match(token):
        return "ip_address"
    if token.upper() in {l.upper() for l in LEVELS}:
        return "level"
    if "=" in token and len(token.split("=", 1)) == 2 and token.split("=", 1)[0].strip():
        return "key_value"
    # Check for pure numeric (could be a PID, port, user ID, etc.)
    try:
        float(token)
        return "numeric"
    except ValueError:
        pass
    return "generic"


def _field_name(token: str, position: int) -> str:
    """Derive a field name for a token based on its type."""
    token = token.strip()
    if not token:
        return f"field_{position}"
    if ISO_TIMESTAMP_RE.match(token):
        return "timestamp"
    if IP_RE.match(token):
        return "ip_address"
    if token.upper() in {l.upper() for l in LEVELS}:
        return "level"
    if "=" in token:
        key, _ = token.split("=", 1)
        key = key.strip()
        if key:
            return key
    return f"field_{position}"


def _split_and_strip(line: str, delimiter: str) -> list[str]:
    """Split a line by delimiter and strip whitespace from each token.

    For space delimiter, we use split() which naturally handles
    multiple consecutive spaces and strips. For other delimiters,
    we split then strip each token individually.
    """
    if delimiter == " ":
        return line.split()
    return [token.strip() for token in line.split(delimiter)]


def _score_delimiter(lines: list[str], delimiter: str) -> tuple[float, float, list[list[str]]]:
    """Score a delimiter candidate. Returns (score, consistency, tokenized_lines).

    The score is a composite of:
    - consistency: fraction of lines that produce the same token count
    - recognized_ratio: fraction of tokens that are recognized types
    - penalizes delimiters that produce only 1 token (delimiter not present)
    """
    if not lines:
        return 0.0, 0.0, []

    tokenized = [_split_and_strip(line, delimiter) for line in lines]
    token_counts = [len(tokens) for tokens in tokenized]

    # If delimiter produces only 1 token for all lines, it's not present
    if all(count <= 1 for count in token_counts):
        return 0.0, 0.0, tokenized

    # Consistency: what fraction of lines have the most common token count?
    count_counter = Counter(token_counts)
    most_common_count, most_common_freq = count_counter.most_common(1)[0]
    consistency = most_common_freq / len(lines)

    # Filter to lines with the dominant token count for recognized-ratio calc
    dominant_lines = [
        tokens for tokens, count in zip(tokenized, token_counts)
        if count == most_common_count
    ]

    # Recognized ratio: across all tokens in dominant lines, what fraction
    # are a recognized type (not "generic" and not "empty")?
    total_tokens = 0
    recognized_tokens = 0
    for tokens in dominant_lines:
        for token in tokens:
            if not token:
                continue
            total_tokens += 1
            ttype = _token_type(token)
            if ttype not in ("generic", "empty"):
                recognized_tokens += 1

    recognized_ratio = recognized_tokens / total_tokens if total_tokens > 0 else 0.0

    # Composite score: consistency matters most, but recognized_ratio
    # breaks ties between delimiters with equal consistency.
    # A small bonus for having more than 1 recognized token total.
    score = consistency * (0.4 + recognized_ratio * 0.6)

    return score, consistency, tokenized


def infer_fields(lines: list[str]) -> dict:
    """Infer field names, types, and confidence from a window of raw log lines.

    Returns a dict with:
    - proposed_fields: {field_name: value} for the last line
    - confidence: 0.0 to 1.0
    - delimiter_used: the chosen delimiter string
    """
    if not lines:
        return {
            "proposed_fields": {},
            "confidence": 0.0,
            "delimiter_used": " ",
        }

    # Filter out empty/whitespace-only lines
    lines = [line for line in lines if line.strip()]
    if not lines:
        return {
            "proposed_fields": {},
            "confidence": 0.0,
            "delimiter_used": " ",
        }

    delimiters = ["|", ",", "\t", " "]
    best_delimiter = " "
    best_score = -1.0
    best_consistency = 0.0
    best_tokenized: list[list[str]] = []

    for delim in delimiters:
        score, consistency, tokenized = _score_delimiter(lines, delim)
        if score > best_score:
            best_score = score
            best_delimiter = delim
            best_consistency = consistency
            best_tokenized = tokenized

    # If nothing scored well, fall back to space
    if best_score <= 0.0:
        best_delimiter = " "
        best_tokenized = [_split_and_strip(line, " ") for line in lines]
        best_consistency = 1.0

    # Determine dominant type per position across all tokenized lines
    max_tokens = max(len(tokens) for tokens in best_tokenized) if best_tokenized else 0
    dominant_types: list[str] = []
    for pos in range(max_tokens):
        types = []
        for tokens in best_tokenized:
            if pos < len(tokens) and tokens[pos]:
                types.append(_token_type(tokens[pos]))
        if types:
            dominant = Counter(types).most_common(1)[0][0]
            dominant_types.append(dominant)
        else:
            dominant_types.append("generic")

    # Build proposed fields for the LAST line
    last_line_tokens = best_tokenized[-1] if best_tokenized else []
    proposed_fields: dict[str, str] = {}
    match_count = 0

    # Handle key=value specially: if any token is key=value, extract both
    # the key name and value. Also handle "= " delimited formats where
    # the entire line is key=value pairs separated by the delimiter.
    for pos, token in enumerate(last_line_tokens):
        if not token:
            continue
        field = _field_name(token, pos)
        if "=" in token and _token_type(token) == "key_value":
            value = token.split("=", 1)[1].strip()
        else:
            value = token
        proposed_fields[field] = value
        if pos < len(dominant_types) and _token_type(token) == dominant_types[pos]:
            match_count += 1

    total_tokens = len([t for t in last_line_tokens if t])
    type_match_fraction = match_count / total_tokens if total_tokens > 0 else 0.0

    # If EVERY column is generic, confidence should be very low —
    # the delimiter might be consistent but we don't understand the data.
    recognized_positions = sum(1 for t in dominant_types if t not in ("generic", "empty"))

    if recognized_positions == 0:
        confidence = 0.0
    else:
        confidence = round(best_consistency * type_match_fraction, 2)

    # Discount confidence when we haven't seen enough lines yet.
    sample_size_factor = min(len(lines) / MIN_SAMPLE_SIZE, 1.0)
    confidence = round(confidence * sample_size_factor, 2)

    confidence = max(0.0, min(1.0, confidence))

    return {
        "proposed_fields": proposed_fields,
        "confidence": confidence,
        "delimiter_used": best_delimiter,
    }
