# Universal Log Framework

A local log pipeline that collects events, parses known formats, infers fields for unknown logs, stores results in ClickHouse, and exposes a Python API for the dashboard.

## Architecture

```text
collector -> Kafka raw-logs -> parser -> parsed-logs -> Go sink -> ClickHouse
                                      \
                                       -> unknown-logs -> inference worker -> inferred-logs -> inferred sink -> ClickHouse

Python gateway API: http://localhost:8000
Dashboard:          http://localhost:5173
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

All commands below assume the repository root is the current directory:

```bash
cd /Users/shivanshumangal/Coding/Projects/universal-log-framework
```

## Quick Start

Use one terminal for Docker and one terminal for each long-running service.

### 1. Start Kafka and ClickHouse

```bash
docker compose -f infra/docker-compose.yml up -d kafka clickhouse
docker compose -f infra/docker-compose.yml ps
```

Check ClickHouse:

```bash
curl -sS -u default:changeme http://localhost:8123/ping
```

Expected response:

```text
Ok.
```

### 2. Create Kafka topics

```bash
docker exec kafka /opt/kafka/bin/kafka-topics.sh --create --if-not-exists \
  --topic unknown-logs --bootstrap-server localhost:9092

docker exec kafka /opt/kafka/bin/kafka-topics.sh --create --if-not-exists \
  --topic inferred-logs --bootstrap-server localhost:9092
```

The collector and parser create their normal topics when Kafka auto-creation is enabled. To create all topics explicitly:

```bash
for topic in raw-logs parsed-logs unknown-logs inferred-logs; do
  docker exec kafka /opt/kafka/bin/kafka-topics.sh --create --if-not-exists \
    --topic "$topic" --bootstrap-server localhost:9092
done
```

### 3. Build the Go services

Terminal 1:

```bash
cd ingestion
make build
```

This builds `collector`, `parser`, `sink`, and `inferredsink` in `ingestion/bin/`.

### 4. Run the collector

Terminal 2:

```bash
cd /Users/shivanshumangal/Coding/Projects/universal-log-framework/ingestion
KAFKA_BROKERS=localhost:9092 ./bin/collector
```

It tails `ingestion/configs/test.log` and listens for syslog on UDP port `514`.

### 5. Run the parser

Terminal 3:

```bash
cd /Users/shivanshumangal/Coding/Projects/universal-log-framework/ingestion
KAFKA_BROKERS=localhost:9092 ./bin/parser
```

### 6. Run the parsed-log sink

Terminal 4:

```bash
cd /Users/shivanshumangal/Coding/Projects/universal-log-framework/ingestion
KAFKA_BROKERS=localhost:9092 \
CLICKHOUSE_ADDR=localhost:9000 \
CLICKHOUSE_DATABASE=logs \
CLICKHOUSE_USERNAME=default \
CLICKHOUSE_PASSWORD=changeme \
./bin/sink
```

### 7. Run the inferred-log sink

Terminal 5:

```bash
cd /Users/shivanshumangal/Coding/Projects/universal-log-framework/ingestion
KAFKA_BROKERS=localhost:9092 \
KAFKA_INFERRED_TOPIC=inferred-logs \
CLICKHOUSE_ADDR=localhost:9000 \
CLICKHOUSE_DATABASE=logs \
CLICKHOUSE_USERNAME=default \
CLICKHOUSE_PASSWORD=changeme \
./bin/inferredsink
```

`inferredsink` consumes `inferred-logs`, stores high-confidence events in `parsed_logs`, and stores lower-confidence events in `review_queue`.

### 8. Run the inference API

The checked-in [inference/.env](inference/.env) is configured for the Docker services when the API runs directly on macOS:

```env
KAFKA_BROKERS=localhost:9092
CLICKHOUSE_URL=http://localhost:8123
CLICKHOUSE_DATABASE=logs
```

Terminal 6:

```bash
cd /Users/shivanshumangal/Coding/Projects/universal-log-framework/inference
source venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Check the API:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/inference/stats
```

The API also serves authenticated gateway routes under `/api`. The configured admin credentials are loaded from `inference/.env`.

### 9. Run the dashboard

Terminal 7:

```bash
cd /Users/shivanshumangal/Coding/Projects/universal-log-framework/dashboard
npm install
npm run dev
```

Open <http://localhost:5173>.

### 10. Send a test log

Terminal 8:

```bash
printf '%s\n' '{"level":"info","msg":"hello"}' >> ingestion/configs/test.log
```

You can also send a syslog message:

```bash
printf '%s\n' '<34>Oct 11 22:14:15 mymachine su: failed for lonvick' | nc -u -w 1 localhost 514
```

### 11. Inspect ClickHouse

```bash
docker exec ch-server clickhouse-client \
  --user default --password changeme --database logs \
  --query 'SHOW TABLES'

docker exec ch-server clickhouse-client \
  --user default --password changeme --database logs \
  --query 'SELECT count() FROM parsed_logs'

docker exec ch-server clickhouse-client \
  --user default --password changeme --database logs \
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
docker compose -f infra/docker-compose.yml ps

# ClickHouse HTTP health
curl -sS -u default:changeme http://localhost:8123/ping

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

Stop local processes with `Ctrl+C`, then stop Docker services:

```bash
docker compose -f infra/docker-compose.yml down
```

Avoid `docker compose down -v` when you want to preserve the bind-mounted ClickHouse data in `infra/ch_data`.

## Service-specific documentation

- [Ingestion README](ingestion/README.md)
- [Inference README](inference/README.md)
- [Infrastructure Compose file](infra/docker-compose.yml)
