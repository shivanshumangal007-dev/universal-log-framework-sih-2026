# Ingestion Layer

Scalable log ingestion built in Go. Collects raw logs via file-tail and syslog UDP, parses known formats, and stores structured events in ClickHouse.

## Complete Pipeline

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  File Tail   │     │ Syslog UDP   │     │   Kafka      │     │   Parsers    │     │   Kafka      │
│  Collector   ├────►│  Listener    ├────►│  raw-logs    ├────►│ JSON,Syslog  ├────►│ parsed-logs  │
│              │     │   :514/udp   │     │   topic      │     │  CSV, CEF    │     │   topic      │
└──────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘     └──────┬───────┘
                                                                      │                    │
                                                                      ▼                    ▼
                                                               ┌──────────────┐     ┌──────────────┐
                                                               │ Kafka        │     │ ClickHouse   │
                                                               │ parsed-logs  │     │ parsed_logs  │
                                                               │ topic        │     │ table        │
                                                               └──────────────┘     └──────────────┘
```

## Folder Layout

```
ingestion/
├── cmd/
│   ├── collector/          # Entrypoint: file-tail + syslog → raw-logs
│   ├── parser/             # Entrypoint: raw-logs → parsed-logs
│   └── sink/               # Entrypoint: parsed-logs → ClickHouse
│   └── inferredsink/       # Entrypoint: inferred-logs → ClickHouse/review_queue
├── internal/
│   ├── collector/
│   │   ├── filetail/       # File tailing logic
│   │   └── syslog/         # UDP syslog listener
│   ├── clickhouse/         # ClickHouse client + schema management
│   ├── kafka/
│   │   ├── producer.go     # Typed Kafka writer
│   │   └── consumer.go     # Typed Kafka reader with commit
│   ├── model/
│   │   └── event.go        # RawEvent + ParsedEvent structs
│   ├── parser/
│   │   ├── parser.go       # JSON, Syslog, CEF, CSV parsers
│   │   └── parser_test.go
│   └── config/
│       └── config.go       # Env-based config loader
├── pkg/
│   └── utils/              # Shared helpers
├── configs/
│   ├── log-samples.jsonl   # Sample logs for testing
│   └── test.log            # Default file-tail target
├── deployments/
│   ├── Dockerfile.collector
│   ├── Dockerfile.parser
│   ├── Dockerfile.sink
│   └── docker-compose.ingestion.yml
├── go.mod / go.sum
├── Makefile
└── README.md
```

## Quick Start

These instructions assume macOS or Linux with Git, Go, Docker, and Docker Compose installed.

### 1. Clone the repository

```bash
git clone <REPOSITORY_URL>
cd universal-log-framework
```

Replace `<REPOSITORY_URL>` with the GitHub URL for this repository. If you already cloned the repository, start from its root directory:

```bash
cd /path/to/universal-log-framework
```

### 2. Start Kafka and ClickHouse

Run this from the repository root:

```bash
docker compose -f infra/docker-compose.yml up -d kafka clickhouse
```

Wait until both services are ready:

```bash
docker compose -f infra/docker-compose.yml ps
```

ClickHouse should show `Up (healthy)`. Verify its authenticated HTTP endpoint:

```bash
curl -sS -u default:changeme 'http://localhost:8123/?query=SELECT%201'
```

Expected output:

```text
1
```

If ClickHouse was previously run with incompatible local data and exits during startup, stop it and move the data directory aside before starting again. This preserves the old data as a backup:

```bash
docker compose -f infra/docker-compose.yml down
mv infra/ch_data infra/ch_data.backup
mkdir infra/ch_data
docker compose -f infra/docker-compose.yml up -d kafka clickhouse
```

Do not use `docker compose down -v` as a substitute for removing `infra/ch_data`; `ch_data` is a bind-mounted directory and is not deleted by that command.

### 3. Create Kafka topics

Create the topics the pipeline expects:

```bash
docker exec kafka /opt/kafka/bin/kafka-topics.sh \
  --create --if-not-exists \
  --topic unknown-logs \
  --bootstrap-server localhost:9092
```

> The `raw-logs` and `parsed-logs` topics are created automatically by the collector and parser on first use when using Kafka 3.x with auto-create enabled. `unknown-logs` may also auto-create, but creating it explicitly ensures it exists before the parser starts.

### 4. Build all binaries

```bash
cd ingestion
make build
```

### 5. Run the collector (Terminal 1)

Run from the `ingestion` directory. Keep this terminal open:

```bash
KAFKA_BROKERS=localhost:9092 ./bin/collector
```

The collector listens for syslog on UDP port `514` and tails `configs/test.log`.

### 6. Run the parser (Terminal 2)

Open a second terminal and run:

```bash
cd /path/to/universal-log-framework/ingestion
KAFKA_BROKERS=localhost:9092 ./bin/parser
```

For a clean test that reads existing records, use a new parser consumer group:

```bash
cd /path/to/universal-log-framework/ingestion
KAFKA_BROKERS=localhost:9092 \
KAFKA_GROUP_ID=parser-test-$(date +%s) \
./bin/parser
```

### 7. Run the ClickHouse sink (Terminal 3)

Open a third terminal and run:

```bash
cd /path/to/universal-log-framework/ingestion
KAFKA_BROKERS=localhost:9092 \
  CLICKHOUSE_ADDR=localhost:9000 \
  CLICKHOUSE_DATABASE=logs \
  CLICKHOUSE_USERNAME=default \
  CLICKHOUSE_PASSWORD=changeme \
  ./bin/sink
```

The sink creates `logs.parsed_logs` automatically and commits Kafka messages only after ClickHouse accepts them.

### 8. Run the inferred sink (Terminal 4)

Open a fourth terminal and run:

```bash
cd /path/to/universal-log-framework/ingestion
KAFKA_BROKERS=localhost:9092 \
  CLICKHOUSE_ADDR=localhost:9000 \
  CLICKHOUSE_DATABASE=logs \
  CLICKHOUSE_USERNAME=default \
  CLICKHOUSE_PASSWORD=changeme \
  ./bin/inferredsink
```

The inferred sink consumes `inferred-logs`. Events at or above the confidence
threshold go to `logs.parsed_logs` with `format='inferred'`; lower-confidence
events go to `logs.review_queue` with `status='pending'`. It creates the review
table automatically and commits Kafka offsets only after a successful insert.

### 9. Send test logs (Terminal 5)

Open a fifth terminal. Run the following from the repository root:

```bash
# Syslog UDP
printf '%s\n' '<34>Oct 11 22:14:15 mymachine su: failed for lonvick' | nc -u -w 1 localhost 514

# JSON to file-tail
printf '%s\n' '{"level":"info","msg":"hello"}' >> ingestion/configs/test.log

# CEF to file-tail
printf '%s\n' 'CEF:0|Security|threatmanager|1.0|100|worm stopped|10|src=10.0.0.1' >> ingestion/configs/test.log
```

### 10. Verify in ClickHouse

Open the ClickHouse client inside the running container:

```bash
docker exec -it ch-server clickhouse-client \
  --user default \
  --password changeme \
  --database logs
```

Then run:

```sql
SHOW TABLES;

SELECT count() FROM parsed_logs;

SELECT count() FROM review_queue;

SELECT event_timestamp, format, source, fields_json, metadata_json
FROM parsed_logs
ORDER BY ingested_at DESC
LIMIT 20;
```

Exit with `exit;`.

The same checks can be run as one-off commands:

```bash
docker exec -it ch-server clickhouse-client \
  --user default \
  --password changeme \
  --database logs \
  --query "SELECT event_id, source, format, fields_json FROM parsed_logs ORDER BY ingested_at DESC LIMIT 20 FORMAT Pretty"
```

Or use the HTTP interface:

```bash
curl -sS -u default:changeme \
  'http://localhost:8123/?database=logs&query=SELECT%20event_id,%20source,%20format,%20fields_json%20FROM%20parsed_logs%20ORDER%20BY%20ingested_at%20DESC%20LIMIT%2020'
```

### Troubleshooting

- If `ch-server` is not `Up (healthy)`, inspect the logs with `docker compose -f infra/docker-compose.yml logs clickhouse`.
- If `SELECT count()` returns `0`, confirm that the collector, parser, and sink are all running and that Kafka has records in `parsed-logs`.
- If the parser prints `handler error: unmarshal raw event`, an invalid non-JSON message was manually written to `raw-logs`; send only JSON-encoded `RawEvent` messages to that topic.
- Run Go commands from `ingestion`, because `go.mod` is located there.

## Environment Variables

### Collector

| Variable                | Default              | Description                |
| ----------------------- | -------------------- | -------------------------- |
| `KAFKA_BROKERS`         | `localhost:9092`     | Kafka broker list          |
| `KAFKA_RAW_TOPIC`       | `raw-logs`           | Topic for raw events       |
| `KAFKA_PARSED_TOPIC`    | `parsed-logs`        | Topic for parsed events    |
| `SYSLOG_BIND`           | `0.0.0.0:514`        | UDP bind address           |
| `FILETAIL_PATHS`        | `./configs/test.log` | Comma-separated file paths |
| `FILETAIL_POLL`         | `500ms`              | File poll interval         |
| `FILETAIL_START_AT_END` | `true`               | Start tailing from EOF     |

### Parser

| Variable              | Default            | Description                                 |
| --------------------- | ------------------ | ------------------------------------------- |
| `KAFKA_BROKERS`       | `localhost:9092`   | Kafka broker list                           |
| `KAFKA_RAW_TOPIC`     | `raw-logs`         | Topic to consume                            |
| `KAFKA_PARSED_TOPIC`  | `parsed-logs`      | Topic for successfully parsed events        |
| `KAFKA_UNKNOWN_TOPIC` | `unknown-logs`     | Topic for events that match no known format |
| `KAFKA_GROUP_ID`      | `log-parser-group` | Consumer group                              |

### Sink

| Variable                    | Default           | Description          |
| --------------------------- | ----------------- | -------------------- |
| `KAFKA_BROKERS`             | `localhost:9092`  | Kafka broker list    |
| `KAFKA_PARSED_TOPIC`        | `parsed-logs`     | Topic to consume     |
| `KAFKA_SINK_GROUP_ID`       | `clickhouse-sink` | Consumer group       |
| `CLICKHOUSE_ADDR`           | `localhost:9000`  | Native TCP address   |
| `CLICKHOUSE_DATABASE`       | `logs`            | Database name        |
| `CLICKHOUSE_USERNAME`       | `default`         | Username             |
| `CLICKHOUSE_PASSWORD`       | `changeme`        | Password             |
| `CLICKHOUSE_BATCH_SIZE`     | `100`             | Batch insert size    |
| `CLICKHOUSE_FLUSH_INTERVAL` | `2s`              | Batch flush interval |

### Inferred sink

| Variable               | Default          | Description                                  |
| ---------------------- | ---------------- | -------------------------------------------- |
| `KAFKA_BROKERS`        | `localhost:9092` | Kafka broker list                            |
| `KAFKA_INFERRED_TOPIC` | `inferred-logs`  | Topic to consume                             |
| `CONFIDENCE_THRESHOLD` | `0.75`           | Minimum confidence stored as inferred output |
| `CLICKHOUSE_ADDR`      | `localhost:9000` | Native TCP address                           |
| `CLICKHOUSE_DATABASE`  | `logs`           | Database name                                |
| `CLICKHOUSE_USERNAME`  | `default`        | Username                                     |
| `CLICKHOUSE_PASSWORD`  | `changeme`       | Password                                     |

## ClickHouse Schema

The sink auto-creates the table on startup:

```sql
CREATE TABLE IF NOT EXISTS logs.parsed_logs (
    event_id UUID,
    source String,
    raw_line String,
    event_timestamp DateTime64(3, 'UTC'),
    format LowCardinality(String),
    fields_json String,
    metadata_json String,
    ingested_at DateTime64(3, 'UTC')
) ENGINE = MergeTree
ORDER BY (event_timestamp, source, event_id);
```

### Idempotency

`event_id` is derived deterministically from `SHA-256(source | raw_line | timestamp | fields | metadata)`. This ensures identical events receive the same ID. If Kafka redelivers a message after a successful insert, ClickHouse `MergeTree` will store both rows (it does not enforce unique keys). For true deduplication at query time, use:

```sql
SELECT * FROM parsed_logs
WHERE event_id IN (
    SELECT argMax(event_id, ingested_at)
    FROM parsed_logs
    GROUP BY event_id
)
```

## Supported Parsers

| Format  | Detection Method | Extracted Fields                                                   |
| ------- | ---------------- | ------------------------------------------------------------------ |
| JSON    | `json.Unmarshal` | All top-level keys                                                 |
| Syslog  | RFC3164 regex    | priority, facility, severity, hostname, message                    |
| CEF     | CEF header regex | version, vendor, product, signature_id, name, severity, extensions |
| CSV     | `encoding/csv`   | col_0, col_1, ... columns array                                    |
| Unknown | Fallback         | Routed to `unknown-logs` topic as unparsed `RawEvent`              |

## Scaling

- **Collectors**: Run multiple instances with different `SYSLOG_BIND` or `FILETAIL_PATHS`.
- **Parsers**: Scale consumer group replicas; Kafka rebalances partitions automatically.
- **Sink**: Scale consumer group replicas; each commits offsets only after successful ClickHouse insertion.
