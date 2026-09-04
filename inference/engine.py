import re
from collections import Counter

# Regex patterns
ISO_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$"
)
IP_RE = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)$"
)
LEVELS = {"INFO", "WARN", "ERROR", "DEBUG", "CRITICAL"}


def _token_type(token: str) -> str:
    if ISO_TIMESTAMP_RE.match(token):
        return "timestamp"
    if IP_RE.match(token):
        return "ip_address"
    if token in LEVELS:
        return "level"
    if "=" in token:
        return "key_value"
    return "generic"


def _field_name(token: str, position: int) -> str:
    if ISO_TIMESTAMP_RE.match(token):
        return "timestamp"
    if IP_RE.match(token):
        return "ip_address"
    if token in LEVELS:
        return "level"
    if "=" in token:
        key, _ = token.split("=", 1)
        return key
    return f"field_{position}"


def _compute_delimiter_consistency(lines: list[str], delimiter: str) -> float:
    if not lines:
        return 0.0
    token_counts = [len(line.split(delimiter)) for line in lines]
    most_common_count = Counter(token_counts).most_common(1)[0][1]
    return most_common_count / len(lines)


def _compute_delimiter_stats(lines: list[str], delimiter: str) -> tuple[float, float]:
    if not lines:
        return 0.0, 0.0
    token_counts = [len(line.split(delimiter)) for line in lines]
    most_common_count = Counter(token_counts).most_common(1)[0][1]
    consistency = most_common_count / len(lines)
    avg_tokens = sum(token_counts) / len(token_counts)
    return consistency, avg_tokens

def infer_fields(lines: list[str]) -> dict:
    if not lines:
        return {
            "proposed_fields": {},
            "confidence": 0.0,
            "delimiter_used": " ",
        }

    delimiters = [" ", ",", "|", "\t", "="]
    best_delimiter = " "
    best_consistency = 0.0

    for delim in delimiters:
        consistency,avg_tokens = _compute_delimiter_stats(lines, delim)
        if avg_tokens <= 1.0:
            continue  # delimiter isn't actually present in these lines
        if consistency > best_consistency and consistency >= 0.6:
            best_consistency = consistency
            best_delimiter = delim

    if best_delimiter is None:
        best_delimiter = " "
        best_consistency = _compute_delimiter_consistency(lines, best_delimiter)
    if best_consistency < 0.6:
        best_delimiter = " "
        best_consistency = _compute_delimiter_consistency(lines, best_delimiter)

    # Tokenize all lines with the chosen delimiter
    tokenized_lines = [line.split(best_delimiter) for line in lines]

    # Determine dominant type per position
    max_tokens = max(len(tokens) for tokens in tokenized_lines)
    dominant_types = []
    for pos in range(max_tokens):
        types = []
        for tokens in tokenized_lines:
            if pos < len(tokens):
                types.append(_token_type(tokens[pos]))
        if types:
            dominant = Counter(types).most_common(1)[0][0]
            dominant_types.append(dominant)
        else:
            dominant_types.append("generic")

        # Build proposed fields for the LAST line
    last_line_tokens = tokenized_lines[-1]
    proposed_fields = {}
    match_count = 0
    for pos, token in enumerate(last_line_tokens):
        field = _field_name(token, pos)
        if "=" in token:
            value = token.split("=", 1)[1]
        else:
            value = token
        proposed_fields[field] = value
        if pos < len(dominant_types) and _token_type(token) == dominant_types[pos]:
            match_count += 1


    total_tokens = len(last_line_tokens)
    type_match_fraction = match_count / total_tokens if total_tokens > 0 else 0.0

    confidence = round(best_consistency * type_match_fraction, 2)
    confidence = max(0.0, min(1.0, confidence))
    return {
        "proposed_fields": proposed_fields,
        "confidence": confidence,
        "delimiter_used": best_delimiter,
    }
