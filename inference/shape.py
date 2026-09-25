"""shape.py — shared log-line shape signature for schema-memory matching.

compute_shape() converts a pre-split, pre-stripped token list into a
single deterministic string like "5|generic,generic,level,kv:user,kv:action".
This signature is stored alongside each learned schema and compared against
the incoming line at lookup time, so a schema is only applied when the
structural layout of the raw line actually matches the training example.

Deliberately kept import-only from engine.py; no new regex patterns here.
"""
from engine import IP_RE, ISO_TIMESTAMP_RE, LEVELS

# Pre-build the uppercase set once for O(1) level lookups.
_LEVELS_UPPER: frozenset[str] = frozenset(lv.upper() for lv in LEVELS)


def compute_shape(tokens: list[str]) -> str:
    """Return a shape signature for an already-split, already-stripped token list.

    Format: "<count>|<slot0>,<slot1>,..."

    Each slot is one of:
      kv:<lowercased-key>   – token matches key=value (both sides non-empty
                              after splitting on the first "=")
      timestamp             – matches engine.ISO_TIMESTAMP_RE
      ip_address            – matches engine.IP_RE
      level                 – in engine.LEVELS (case-insensitive)
      numeric               – parses as float()
      generic               – everything else

    The kv check runs first because a token like "user=3" would otherwise
    fall through to "generic" or "numeric" before its key= structure is
    recognised.  The token count is included in the prefix so that lines
    with different numbers of fields can never accidentally match a stored
    schema — this is the fix for Bug 2 (different-length lines from the
    same source being silently truncated/padded).
    """
    slots: list[str] = []
    for token in tokens:
        # --- key=value check (must be first) ---
        if "=" in token:
            parts = token.split("=", 1)
            key = parts[0].strip()
            val = parts[1].strip()
            if key and val:
                slots.append(f"kv:{key.lower()}")
                continue

        # --- well-known semantic types ---
        if ISO_TIMESTAMP_RE.match(token):
            slots.append("timestamp")
        elif IP_RE.match(token):
            slots.append("ip_address")
        elif token.upper() in _LEVELS_UPPER:
            slots.append("level")
        else:
            try:
                float(token)
                slots.append("numeric")
            except ValueError:
                slots.append("generic")

    return f"{len(tokens)}|{','.join(slots)}"
