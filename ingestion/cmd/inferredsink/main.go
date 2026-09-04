package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	ch "github.com/shivanshumangal-dev/log-ingestion-sih/internal/clickhouse"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/config"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/kafka"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/model"
)

type inferredEvent struct {
	Source         string            `json:"source"`
	RawLine        string            `json:"raw_line"`
	ProposedFields map[string]string `json:"proposed_fields"`
	Confidence     float64           `json:"confidence"`
	DelimiterUsed  string            `json:"delimiter_used"`
	InferredAt     time.Time         `json:"inferred_at"`
}

func main() {
	cfg := config.LoadInferredSink()
	fmt.Printf("inferred sink starting | kafka=%s | clickhouse=%s/%s | threshold=%.2f\n", cfg.Kafka, cfg.ClickHouse.Addr, cfg.ClickHouse.Database, cfg.ConfidenceThreshold)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	go func() { <-sig; fmt.Println("shutting down inferred sink..."); cancel() }()

	client, err := ch.NewClient(ch.Config{Addr: cfg.ClickHouse.Addr, Database: cfg.ClickHouse.Database, Username: cfg.ClickHouse.Username, Password: cfg.ClickHouse.Password, BatchSize: cfg.ClickHouse.BatchSize, FlushInterval: cfg.ClickHouse.FlushInterval})
	if err != nil {
		fmt.Printf("clickhouse connect failed: %v\n", err)
		os.Exit(1)
	}
	defer client.Close()

	createCtx, createCancel := context.WithTimeout(ctx, 10*time.Second)
	err = client.CreateReviewQueue(createCtx)
	createCancel()
	if err != nil {
		fmt.Printf("clickhouse create review queue failed: %v\n", err)
		os.Exit(1)
	}

	consumer := kafka.NewConsumerForTopic(cfg.Kafka, cfg.Kafka.InferredTopic)
	defer consumer.Close()
	err = consumer.Run(ctx, func(ctx context.Context, key, value []byte) (bool, error) {
		var input inferredEvent
		if err := json.Unmarshal(value, &input); err != nil {
			fmt.Printf("decode error: %v | payload=%s\n", err, string(value))
			return false, nil
		}
		if input.Source == "" || input.InferredAt.IsZero() {
			return false, fmt.Errorf("inferred event missing source or inferred_at")
		}

		fields := make(map[string]interface{}, len(input.ProposedFields))
		for name, value := range input.ProposedFields {
			fields[name] = value
		}
		ev := model.ParsedEvent{
			Source: input.Source, RawLine: input.RawLine, Timestamp: input.InferredAt.UTC(), Format: "inferred",
			Fields: fields,
			Metadata: map[string]string{
				"delimiter_used": input.DelimiterUsed,
				"confidence":     strconv.FormatFloat(input.Confidence, 'f', -1, 64),
			},
		}

		var insertErr error
		if input.Confidence >= cfg.ConfidenceThreshold {
			insertErr = client.Insert(ctx, ev)
		} else {
			insertErr = client.InsertReview(ctx, ev, input.Confidence)
		}
		if insertErr != nil {
			return false, fmt.Errorf("clickhouse insert failed: %w", insertErr)
		}
		return true, nil
	})
	if err != nil && err != context.Canceled {
		fmt.Printf("inferred sink exited: %v\n", err)
		os.Exit(1)
	}
}
