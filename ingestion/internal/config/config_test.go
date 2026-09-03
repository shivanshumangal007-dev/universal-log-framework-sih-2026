package config

import (
	"testing"
	"time"
)

func TestLoadSinkDefaults(t *testing.T) {
	cfg := LoadSink()

	if len(cfg.Kafka.Brokers) != 1 || cfg.Kafka.Brokers[0] != "localhost:9092" {
		t.Fatalf("unexpected brokers: %v", cfg.Kafka.Brokers)
	}
	if cfg.Kafka.ParsedTopic != "parsed-logs" {
		t.Fatalf("unexpected parsed topic: %s", cfg.Kafka.ParsedTopic)
	}
	if cfg.Kafka.GroupID != "clickhouse-sink" {
		t.Fatalf("unexpected group id: %s", cfg.Kafka.GroupID)
	}
	if cfg.ClickHouse.Addr != "localhost:9000" {
		t.Fatalf("unexpected clickhouse addr: %s", cfg.ClickHouse.Addr)
	}
	if cfg.ClickHouse.Database != "logs" {
		t.Fatalf("unexpected database: %s", cfg.ClickHouse.Database)
	}
	if cfg.ClickHouse.Username != "default" {
		t.Fatalf("unexpected username: %s", cfg.ClickHouse.Username)
	}
	if cfg.ClickHouse.Password != "changeme" {
		t.Fatalf("unexpected password: %s", cfg.ClickHouse.Password)
	}
	if cfg.ClickHouse.BatchSize != 100 {
		t.Fatalf("unexpected batch size: %d", cfg.ClickHouse.BatchSize)
	}
	if cfg.ClickHouse.FlushInterval != 2*time.Second {
		t.Fatalf("unexpected flush interval: %v", cfg.ClickHouse.FlushInterval)
	}
}
