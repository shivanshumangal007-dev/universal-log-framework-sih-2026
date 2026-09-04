# Inference Service

The service consumes unknown log events from Kafka, groups recent lines by their
`source`, and publishes a field proposal for every new line.

## Algorithm

For each source, the service keeps at most 50 recent lines and removes lines
older than five minutes. It tests spaces, commas, pipes, tabs, and equals signs
as possible delimiters. The delimiter whose lines most often have the same
number of tokens wins, provided that at least 60% of the lines agree. If no
delimiter reaches that threshold, spaces are used as the fallback.

Each token position is compared across the window. Recognized timestamps,
IP addresses, and log levels receive those names; `key=value` tokens use the
key; other tokens receive names such as `field_3`. Confidence combines delimiter
consistency with the fraction of the newest line whose token types match the
dominant type at each position.

## Worked example

Clean sample line:

```text
2023-01-01T00:00:00Z 192.168.1.1 INFO started
```

With similar lines in the window, the inferred output is:

```json
{
	"proposed_fields": {
		"timestamp": "2023-01-01T00:00:00Z",
		"ip_address": "192.168.1.1",
		"level": "INFO",
		"field_3": "started"
	},
	"confidence": 1.0,
	"delimiter_used": " "
}
```

Garbage line:

```text
not really a structured log
```

The output falls back to positional generic fields because the tokens are not
recognized:

```json
{
	"proposed_fields": {
		"field_0": "not",
		"field_1": "really",
		"field_2": "a",
		"field_3": "structured",
		"field_4": "log"
	},
	"confidence": 1.0,
	"delimiter_used": " "
}
```

The Kafka output also includes `source`, `raw_line`, and an ISO8601
`inferred_at` timestamp. `GET /inference/stats` reports recent line counts and
average confidence per source.

## Run locally

```bash
cd inference
uv pip install -r requirements.txt
python main.py
```
