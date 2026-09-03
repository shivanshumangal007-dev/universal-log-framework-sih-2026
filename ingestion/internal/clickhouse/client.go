package clickhouse

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/model"
)

// Client wraps a ClickHouse connection with helpers for log ingestion.
type Client struct {
	conn          driver.Conn
	database      string
	table         string
	batchSize     int
	flushInterval time.Duration
}

// Config holds ClickHouse connection settings.
type Config struct {
	Addr          string
	Database      string
	Username      string
	Password      string
	BatchSize     int
	FlushInterval time.Duration
}

// NewClient connects to ClickHouse and returns a Client.
func NewClient(cfg Config) (*Client, error) {
	conn, err := clickhouse.Open(&clickhouse.Options{
		Addr: []string{cfg.Addr},
		Auth: clickhouse.Auth{
			Database: cfg.Database,
			Username: cfg.Username,
			Password: cfg.Password,
		},
		DialTimeout:  5 * time.Second,
		MaxOpenConns: 10,
		MaxIdleConns: 5,
	})
	if err != nil {
		return nil, fmt.Errorf("clickhouse open: %w", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := conn.Ping(ctx); err != nil {
		return nil, fmt.Errorf("clickhouse ping: %w", err)
	}

	return &Client{
		conn:          conn,
		database:      cfg.Database,
		table:         "parsed_logs",
		batchSize:     cfg.BatchSize,
		flushInterval: cfg.FlushInterval,
	}, nil
}

// Close closes the ClickHouse connection.
func (c *Client) Close() error {
	return c.conn.Close()
}

// CreateTable creates the parsed_logs table if it does not exist.
func (c *Client) CreateTable(ctx context.Context) error {
	query := fmt.Sprintf(`CREATE TABLE IF NOT EXISTS %s.%s (
		event_id UUID,
		source String,
		raw_line String,
		event_timestamp DateTime64(3, 'UTC'),
		format LowCardinality(String),
		fields_json String,
		metadata_json String,
		ingested_at DateTime64(3, 'UTC')
	) ENGINE = MergeTree
	ORDER BY (event_timestamp, source, event_id)`, c.database, c.table)

	return c.conn.Exec(ctx, query)
}

// EventID derives a deterministic UUID-like string from event contents.
// This makes inserts idempotent for identical events.
func EventID(ev model.ParsedEvent) string {
	fieldsJSON, _ := json.Marshal(ev.Fields)
	metaJSON, _ := json.Marshal(ev.Metadata)
	h := sha256.New()
	fmt.Fprintf(h, "%s|%s|%s|%s|%s", ev.Source, ev.RawLine, ev.Timestamp.Format(time.RFC3339Nano), fieldsJSON, metaJSON)
	return hex.EncodeToString(h.Sum(nil))[:32]
}

// Insert stores a single ParsedEvent into ClickHouse.
func (c *Client) Insert(ctx context.Context, ev model.ParsedEvent) error {
	fieldsJSON, err := json.Marshal(ev.Fields)
	if err != nil {
		return fmt.Errorf("marshal fields: %w", err)
	}
	metaJSON, err := json.Marshal(ev.Metadata)
	if err != nil {
		return fmt.Errorf("marshal metadata: %w", err)
	}

	query := fmt.Sprintf(`INSERT INTO %s.%s (event_id, source, raw_line, event_timestamp, format, fields_json, metadata_json, ingested_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`, c.database, c.table)

	return c.conn.Exec(ctx, query,
		EventID(ev),
		ev.Source,
		ev.RawLine,
		ev.Timestamp,
		ev.Format,
		string(fieldsJSON),
		string(metaJSON),
		time.Now().UTC(),
	)
}

// InsertBatch stores multiple ParsedEvents into ClickHouse in a single batch.
func (c *Client) InsertBatch(ctx context.Context, events []model.ParsedEvent) error {
	if len(events) == 0 {
		return nil
	}

	batch, err := c.conn.PrepareBatch(ctx, fmt.Sprintf("INSERT INTO %s.%s (event_id, source, raw_line, event_timestamp, format, fields_json, metadata_json, ingested_at)", c.database, c.table))
	if err != nil {
		return fmt.Errorf("prepare batch: %w", err)
	}

	for _, ev := range events {
		fieldsJSON, err := json.Marshal(ev.Fields)
		if err != nil {
			return fmt.Errorf("marshal fields: %w", err)
		}
		metaJSON, err := json.Marshal(ev.Metadata)
		if err != nil {
			return fmt.Errorf("marshal metadata: %w", err)
		}

		if err := batch.Append(
			EventID(ev),
			ev.Source,
			ev.RawLine,
			ev.Timestamp,
			ev.Format,
			string(fieldsJSON),
			string(metaJSON),
			time.Now().UTC(),
		); err != nil {
			return fmt.Errorf("batch append: %w", err)
		}
	}

	if err := batch.Send(); err != nil {
		return fmt.Errorf("batch send: %w", err)
	}
	return nil
}
