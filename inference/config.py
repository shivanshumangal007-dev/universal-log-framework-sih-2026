import os
from dotenv import load_dotenv

load_dotenv()

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "")
if KAFKA_BROKERS == "":
    raise ValueError("KAFKA_BROKERS environment variable is not set")

KAFKA_UNKNOWN_TOPIC = os.getenv("KAFKA_UNKNOWN_TOPIC", "unknown-logs")
KAFKA_INFERRED_TOPIC = os.getenv("KAFKA_INFERRED_TOPIC", "inferred-logs")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "inference-engine")

# Auth
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    raise ValueError("JWT_SECRET environment variable is not set")

# ClickHouse
CLICKHOUSE_URL = os.getenv("CLICKHOUSE_URL", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "logs")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")

# CORS
DASHBOARD_ORIGIN = os.getenv("DASHBOARD_ORIGIN", "http://localhost:5173")
