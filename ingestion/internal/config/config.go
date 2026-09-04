package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

// Kafka holds producer/consumer settings.
type Kafka struct {
	Brokers       []string
	RawTopic      string
	ParsedTopic   string
	UnknownTopic  string
	InferredTopic string
	GroupID       string
	WriteTimeout  time.Duration
	ReadTimeout   time.Duration
}

// InferredSink is the configuration for inferred event storage.
type InferredSink struct {
	Kafka               Kafka
	ClickHouse          ClickHouseConfig
	ConfidenceThreshold float64
}

// FileTail holds file collector settings.
type FileTail struct {
	Paths        []string
	PollInterval time.Duration
	StartAtEnd   bool
}

// Syslog holds UDP syslog listener settings.
type Syslog struct {
	BindAddr string
	BufferKB int
}

// Collector is the full collector config.
type Collector struct {
	Kafka    Kafka
	FileTail FileTail
	Syslog   Syslog
}

// Parser is the full parser config.
type Parser struct {
	Kafka Kafka
}

// ClickHouseConfig holds ClickHouse connection settings.
type ClickHouseConfig struct {
	Addr          string
	Database      string
	Username      string
	Password      string
	BatchSize     int
	FlushInterval time.Duration
}

// Sink holds the full sink config.
type Sink struct {
	Kafka      Kafka
	ClickHouse ClickHouseConfig
}

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func envInt(key string, def int) int {
	v := os.Getenv(key)
	if v == "" {
		return def
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return def
	}
	return n
}

func envFloat(key string, def float64) float64 {
	v := os.Getenv(key)
	if v == "" {
		return def
	}
	n, err := strconv.ParseFloat(v, 64)
	if err != nil {
		return def
	}
	return n
}

func envDuration(key string, def time.Duration) time.Duration {
	v := os.Getenv(key)
	if v == "" {
		return def
	}
	d, err := time.ParseDuration(v)
	if err != nil {
		return def
	}
	return d
}

// LoadCollector returns Collector populated from env vars with defaults.
func LoadCollector() Collector {
	paths := []string{"./configs/test.log"}
	if p := os.Getenv("FILETAIL_PATHS"); p != "" {
		paths = strings.Split(p, ",")
	}
	return Collector{
		Kafka: Kafka{
			Brokers:      []string{envOr("KAFKA_BROKERS", "localhost:9092")},
			RawTopic:     envOr("KAFKA_RAW_TOPIC", "raw-logs"),
			ParsedTopic:  envOr("KAFKA_PARSED_TOPIC", "parsed-logs"),
			WriteTimeout: envDuration("KAFKA_WRITE_TIMEOUT", 10*time.Second),
			ReadTimeout:  envDuration("KAFKA_READ_TIMEOUT", 10*time.Second),
		},
		FileTail: FileTail{
			Paths:        paths,
			PollInterval: envDuration("FILETAIL_POLL", 500*time.Millisecond),
			StartAtEnd:   envOr("FILETAIL_START_AT_END", "true") == "true",
		},
		Syslog: Syslog{
			BindAddr: envOr("SYSLOG_BIND", "0.0.0.0:514"),
			BufferKB: envInt("SYSLOG_BUFFER_KB", 64),
		},
	}
}

// LoadParser returns Parser populated from env vars with defaults.
func LoadParser() Parser {
	return Parser{
		Kafka: Kafka{
			Brokers:      []string{envOr("KAFKA_BROKERS", "localhost:9092")},
			RawTopic:     envOr("KAFKA_RAW_TOPIC", "raw-logs"),
			ParsedTopic:  envOr("KAFKA_PARSED_TOPIC", "parsed-logs"),
			UnknownTopic: envOr("KAFKA_UNKNOWN_TOPIC", "unknown-logs"),
			GroupID:      envOr("KAFKA_GROUP_ID", "log-parser-group"),
			ReadTimeout:  envDuration("KAFKA_READ_TIMEOUT", 10*time.Second),
			WriteTimeout: envDuration("KAFKA_WRITE_TIMEOUT", 10*time.Second),
		},
	}
}

// LoadSink returns Sink populated from env vars with defaults.
func LoadSink() Sink {
	return Sink{
		Kafka: Kafka{
			Brokers:      []string{envOr("KAFKA_BROKERS", "localhost:9092")},
			RawTopic:     envOr("KAFKA_RAW_TOPIC", "raw-logs"),
			ParsedTopic:  envOr("KAFKA_PARSED_TOPIC", "parsed-logs"),
			GroupID:      envOr("KAFKA_SINK_GROUP_ID", "clickhouse-sink"),
			ReadTimeout:  envDuration("KAFKA_READ_TIMEOUT", 10*time.Second),
			WriteTimeout: envDuration("KAFKA_WRITE_TIMEOUT", 10*time.Second),
		},
		ClickHouse: ClickHouseConfig{
			Addr:          envOr("CLICKHOUSE_ADDR", "localhost:9000"),
			Database:      envOr("CLICKHOUSE_DATABASE", "logs"),
			Username:      envOr("CLICKHOUSE_USERNAME", "default"),
			Password:      envOr("CLICKHOUSE_PASSWORD", "changeme"),
			BatchSize:     envInt("CLICKHOUSE_BATCH_SIZE", 100),
			FlushInterval: envDuration("CLICKHOUSE_FLUSH_INTERVAL", 2*time.Second),
		},
	}
}

// LoadInferredSink returns inferred sink settings populated from env vars.
func LoadInferredSink() InferredSink {
	return InferredSink{
		Kafka: Kafka{
			Brokers:       []string{envOr("KAFKA_BROKERS", "localhost:9092")},
			InferredTopic: envOr("KAFKA_INFERRED_TOPIC", "inferred-logs"),
			GroupID:       "inferred-sink",
			ReadTimeout:   envDuration("KAFKA_READ_TIMEOUT", 10*time.Second),
			WriteTimeout:  envDuration("KAFKA_WRITE_TIMEOUT", 10*time.Second),
		},
		ClickHouse: ClickHouseConfig{
			Addr:          envOr("CLICKHOUSE_ADDR", "localhost:9000"),
			Database:      envOr("CLICKHOUSE_DATABASE", "logs"),
			Username:      envOr("CLICKHOUSE_USERNAME", "default"),
			Password:      envOr("CLICKHOUSE_PASSWORD", "changeme"),
			BatchSize:     envInt("CLICKHOUSE_BATCH_SIZE", 100),
			FlushInterval: envDuration("CLICKHOUSE_FLUSH_INTERVAL", 2*time.Second),
		},
		ConfidenceThreshold: envFloat("CONFIDENCE_THRESHOLD", 0.75),
	}
}

func (k Kafka) String() string {
	return fmt.Sprintf("brokers=%v raw=%s parsed=%s unknown=%s group=%s", k.Brokers, k.RawTopic, k.ParsedTopic, k.UnknownTopic, k.GroupID)
}
