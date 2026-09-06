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

# A window of 1 line always scores perfect delimiter-consistency and
# perfect type-match trivially (there's nothing to disagree with yet),
# which used to produce confidence == 1.0 on a single garbage line.
# Require this many samples before confidence is allowed to reach its
# full computed value; below it, confidence is scaled down linearly.
MIN_SAMPLE_SIZE = 3


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

    # "generic" means a position didn't match any recognized type at
    # all (not a timestamp, ip, level, or key=value). If EVERY column
    # is generic, the lines might still be perfectly consistent with
    # each other in shape (e.g. same word count every time) without
    # containing anything actually recognizable — that used to still
    # score a perfect match fraction, since "all generic, matching
    # every time" looked identical to "all timestamps, matching every
    # time" under this math. Zero it out in that case specifically;
    # a line with at least one recognized column is left untouched.
    recognized_positions = sum(1 for t in dominant_types if t != "generic")

    if recognized_positions == 0:
        confidence = 0.0
    else:
        confidence = round(best_consistency * type_match_fraction, 2)

    # Discount confidence when we haven't seen enough lines from this
    # source yet — a window of 1 trivially scores perfect consistency
    # and perfect type-match against itself, which isn't a meaningful
    # signal. Scale linearly up to MIN_SAMPLE_SIZE, full confidence
    # only once we've actually seen enough lines to judge consistency.
    sample_size_factor = min(len(lines) / MIN_SAMPLE_SIZE, 1.0)
    confidence = round(confidence * sample_size_factor, 2)

    confidence = max(0.0, min(1.0, confidence))
    return {
        "proposed_fields": proposed_fields,
        "confidence": confidence,
        "delimiter_used": best_delimiter,
    }
