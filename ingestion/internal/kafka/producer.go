package kafka

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/segmentio/kafka-go"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/config"
)

// Producer wraps a kafka.Writer for typed publishing.
type Producer struct {
	writer *kafka.Writer
}

// NewProducer creates a producer for the given topic.
func NewProducer(cfg config.Kafka, topic string) *Producer {
	return &Producer{
		writer: &kafka.Writer{
			Addr:         kafka.TCP(cfg.Brokers...),
			Topic:        topic,
			Balancer:     &kafka.LeastBytes{},
			WriteTimeout: cfg.WriteTimeout,
		},
	}
}

// Publish marshals v to JSON and sends it to Kafka.
func (p *Producer) Publish(ctx context.Context, key string, v interface{}) error {
	b, err := json.Marshal(v)
	if err != nil {
		return fmt.Errorf("marshal: %w", err)
	}
	msg := kafka.Message{
		Key:   []byte(key),
		Value: b,
		Time:  time.Now(),
	}
	return p.writer.WriteMessages(ctx, msg)
}

// Close flushes and shuts down the writer.
func (p *Producer) Close() error {
	return p.writer.Close()
}
