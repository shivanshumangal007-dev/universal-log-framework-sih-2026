package kafka

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/segmentio/kafka-go"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/config"
)

// Handler processes a single message. Return true to commit, false to skip.
type Handler func(ctx context.Context, key []byte, value []byte) (commit bool, err error)

// Consumer wraps a kafka.Reader.
type Consumer struct {
	reader *kafka.Reader
}

// NewConsumer creates a consumer for the raw-logs topic.
func NewConsumer(cfg config.Kafka) *Consumer {
	return &Consumer{
		reader: kafka.NewReader(kafka.ReaderConfig{
			Brokers:     cfg.Brokers,
			Topic:       cfg.RawTopic,
			GroupID:     cfg.GroupID,
			MinBytes:    1,
			MaxBytes:    10e6,
			StartOffset: kafka.FirstOffset,
		}),
	}
}

// Run polls messages and dispatches them to h until ctx is cancelled.
func (c *Consumer) Run(ctx context.Context, h Handler) error {
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		m, err := c.reader.ReadMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			return fmt.Errorf("read message: %w", err)
		}

		commit, herr := h(ctx, m.Key, m.Value)
		if herr != nil {
			// Log and continue; dead-letter can be added later.
			fmt.Printf("handler error: %v\n", herr)
			continue
		}
		if commit {
			if err := c.reader.CommitMessages(ctx, m); err != nil {
				fmt.Printf("commit error: %v\n", err)
			}
		}
	}
}

// Close shuts down the reader.
func (c *Consumer) Close() error {
	return c.reader.Close()
}

// UnmarshalJSON is a helper to decode JSON values.
func UnmarshalJSON(data []byte, v interface{}) error {
	return json.Unmarshal(data, v)
}
