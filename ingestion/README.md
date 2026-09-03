# Ingestion Layer

Scalable log ingestion built in Go. Collects raw logs via file-tail and syslog UDP, publishes to Kafka `raw-logs`, then parsers extract structured JSON to `parsed-logs`.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  File Tail   │     │ Syslog UDP   │     │   Kafka      │     │   Parsers    │
│  Collector   ├────►│  Listener    ├────►│  raw-logs    ├────►│ JSON,Syslog  │
│              │     │   :514/udp   │     │   topic      │     │  CSV, CEF    │
└──────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
                                                                      │
                                                                      ▼
                                                               ┌──────────────┐
                                                               │ Kafka        │
                                                               │ parsed-logs  │
                                                               │ topic        │
                                                               └──────────────┘
```

## Folder Layout

```
ingestion/
├── cmd/
│   ├── collector/          # Entrypoint: file-tail + syslog
│   └── parser/             # Entrypoint: consume raw, emit parsed
├── internal/
│   ├── collector/
│   │   ├── filetail/       # File tailing logic
│   │   └── syslog/         # UDP syslog listener
│   ├── kafka/
│   │   ├── producer.go     # Typed Kafka writer
│   │   └── consumer.go     # Typed Kafka reader with commit
│   ├── model/
│   │   └── event.go        # RawEvent + ParsedEvent structs
│   ├── parser/
│   │   └── parser.go       # JSON, Syslog, CEF, CSV parsers
│   └── config/
│       └── config.go       # Env-based config loader
├── pkg/
│   └── utils/              # Shared helpers (extend here)
├── configs/
│   └── log-samples.jsonl   # Sample logs for testing
├── deployments/
│   ├── Dockerfile.collector
│   ├── Dockerfile.parser
│   └── docker-compose.ingestion.yml
├── go.mod / go.sum
├── Makefile
└── README.md
```

## Quick Start

### 1. Start Kafka
```bash
cd ../infra && docker compose up -d kafka
```

### 2. Build
```bash
cd ingestion && make build
```

### 3. Run Collector
```bash
KAFKA_BROKERS=localhost:9092 ./bin/collector
```

### 4. Run Parser
```bash
KAFKA_BROKERS=localhost:9092 ./bin/parser
```

### 5. Send Test Logs
```bash
# Syslog UDP
echo "<34>Oct 11 22:14:15 mymachine su: failed for lonvick" | nc -u localhost 514

# JSON echo to file (configure FILETAIL_PATHS)
echo '{"level":"info","msg":"hello"}' >> /var/log/sample.log
```

## Environment Variables

| Variable              | Default               | Description                     |
|-----------------------|-----------------------|---------------------------------|
| `KAFKA_BROKERS`       | `localhost:9092`      | Kafka broker list               |
| `KAFKA_RAW_TOPIC`     | `raw-logs`            | Topic for raw events            |
| `KAFKA_PARSED_TOPIC`  | `parsed-logs`         | Topic for parsed events         |
| `KAFKA_GROUP_ID`      | `log-parser-group`    | Consumer group for parser       |
| `SYSLOG_BIND`         | `0.0.0.0:514`         | UDP bind address                |
| `FILETAIL_PATHS`      | `/var/log/syslog`     | Comma-separated file paths      |
| `FILETAIL_POLL`       | `500ms`               | File poll interval              |
| `FILETAIL_START_AT_END`| `true`               | Start tailing from EOF          |

## Supported Parsers

| Format  | Detection Method           | Extracted Fields                        |
|---------|---------------------------|------------------------------------------|
| JSON    | `json.Unmarshal`          | All top-level keys                       |
| Syslog  | RFC3164 regex             | priority, facility, severity, hostname, message |
| CEF     | CEF header regex          | version, vendor, product, signature_id, name, severity, extensions |
| CSV     | `encoding/csv`            | col_0, col_1, ... columns array          |
| Unknown | Fallback                  | Empty fields, passthrough                |

## Scaling

- **Collectors**: Run multiple instances with different `SYSLOG_BIND` or `FILETAIL_PATHS`.
- **Parsers**: Scale consumer group replicas; Kafka rebalances partitions automatically.
