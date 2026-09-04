import os
from dotenv import load_dotenv

load_dotenv()

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "")
if KAFKA_BROKERS == "":
    raise ValueError("KAFKA_BROKERS environment variable is not set")


KAFKA_UNKNOWN_TOPIC = os.getenv("KAFKA_UNKNOWN_TOPIC", "unknown-logs")
KAFKA_INFERRED_TOPIC = os.getenv("KAFKA_INFERRED_TOPIC", "inferred-logs")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "inference-engine")
