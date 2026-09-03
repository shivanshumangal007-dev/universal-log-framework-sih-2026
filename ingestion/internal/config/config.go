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
	Brokers      []string
	RawTopic     string
	ParsedTopic  string
	GroupID      string
	WriteTimeout time.Duration
	ReadTimeout  time.Duration
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
			GroupID:      envOr("KAFKA_GROUP_ID", "log-parser-group"),
			ReadTimeout:  envDuration("KAFKA_READ_TIMEOUT", 10*time.Second),
			WriteTimeout: envDuration("KAFKA_WRITE_TIMEOUT", 10*time.Second),
		},
	}
}

func (k Kafka) String() string {
	return fmt.Sprintf("brokers=%v raw=%s parsed=%s group=%s", k.Brokers, k.RawTopic, k.ParsedTopic, k.GroupID)
}
