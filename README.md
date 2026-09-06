# Universal Log Framework

A local log pipeline that collects events, parses known formats, infers fields for unknown logs, stores results in ClickHouse, and exposes a Python API for the dashboard.

## Architecture

```text
collector -> Kafka raw-logs -> parser -> parsed-logs -> Go sink -> ClickHouse
                                      \
                                       -> unknown-logs -> inference worker -> inferred-logs -> inferred sink -> ClickHouse

Python gateway API: http://localhost:8000
Dashboard:          http://localhost:3000
Kafka:              localhost:9092
ClickHouse HTTP:    http://localhost:8123
ClickHouse native:  localhost:9000
```

## Requirements

Install or start:

- Docker and Docker Compose
- Go
- Python 3.11+
- Node.js and npm


## Quick Start

The root Compose file starts the complete pipeline, including the inferred sink that writes low-confidence events to `review_queue`.

Create a root `.env` file with the values required by Compose and the inference API, then run:

```bash
docker compose up -d --build
docker compose ps
```

The services are available at:

- Dashboard: <http://localhost:3000>
- Inference API: <http://localhost:8000>
- ClickHouse HTTP: <http://localhost:8123>
- Kafka: `localhost:9092`

Check service health:

```bash
curl -sS http://localhost:8000/health
curl -sS http://localhost:8123/ping
```

Kafka topics are created automatically by the running services when Kafka auto-creation is enabled. To create them explicitly:

```bash
for topic in raw-logs parsed-logs unknown-logs inferred-logs; do
  docker exec kafka /opt/kafka/bin/kafka-topics.sh --create --if-not-exists \
    --topic "$topic" --bootstrap-server localhost:9092
done

```

### Send a test log

```bash
printf '%s\n' '{"level":"info","msg":"hello"}' >> ingestion/configs/test.log
```

You can also send a syslog message:

```bash
printf '%s\n' '<34>Oct 11 22:14:15 mymachine su: failed for lonvick' | nc -u -w 1 localhost 514
```

### Inspect ClickHouse

```bash
set -a; source .env; set +a

docker exec ch-server clickhouse-client \
  --user default --password "$CLICKHOUSE_PASSWORD" --database logs \
  --query 'SHOW TABLES'

docker exec ch-server clickhouse-client \
  --user default --password "$CLICKHOUSE_PASSWORD" --database logs \
  --query 'SELECT count() FROM parsed_logs'

docker exec ch-server clickhouse-client \
  --user default --password "$CLICKHOUSE_PASSWORD" --database logs \
  --query 'SELECT count() FROM review_queue'
```

## Important hostnames

When services run directly on macOS, use published host ports:

```env
KAFKA_BROKERS=localhost:9092
CLICKHOUSE_URL=http://localhost:8123
CLICKHOUSE_ADDR=localhost:9000
```

When a service runs inside the same Docker network as ClickHouse, use the container hostname instead:

```env
CLICKHOUSE_URL=http://ch-server:8123
CLICKHOUSE_ADDR=ch-server:9000
```

`ch-server` is not resolvable from a process running directly on macOS.

## Useful checks

```bash
# Service status
docker compose ps

# ClickHouse HTTP health
curl -sS http://localhost:8123/ping

# Kafka topics
docker exec kafka /opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092

# Go tests
cd ingestion && go test ./...

# Python tests
cd inference && ./venv/bin/python -m pytest engine_test.py -q

# Dashboard production build
cd dashboard && npm run build
```

## Stop services

Stop the complete stack with:

```bash
docker compose down
```

Avoid `docker compose down -v` when you want to preserve the bind-mounted ClickHouse data in `infra/ch_data`.

## Service-specific documentation

- [Ingestion README](ingestion/README.md)
- [Inference README](inference/README.md)
- [Root Compose file](docker-compose.yml)
