package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	ch "github.com/shivanshumangal-dev/log-ingestion-sih/internal/clickhouse"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/config"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/kafka"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/model"
)

func main() {
	cfg := config.LoadSink()
	fmt.Printf("sink starting | kafka=%s | clickhouse=%s/%s\n", cfg.Kafka, cfg.ClickHouse.Addr, cfg.ClickHouse.Database)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sig
		fmt.Println("shutting down sink...")
		cancel()
	}()

	// Connect to ClickHouse.
	client, err := ch.NewClient(ch.Config{
		Addr:          cfg.ClickHouse.Addr,
		Database:      cfg.ClickHouse.Database,
		Username:      cfg.ClickHouse.Username,
		Password:      cfg.ClickHouse.Password,
		BatchSize:     cfg.ClickHouse.BatchSize,
		FlushInterval: cfg.ClickHouse.FlushInterval,
	})
	if err != nil {
		fmt.Printf("clickhouse connect failed: %v\n", err)
		os.Exit(1)
	}
	defer client.Close()

	// Auto-create table.
	createCtx, createCancel := context.WithTimeout(ctx, 10*time.Second)
	if err := client.CreateTable(createCtx); err != nil {
		createCancel()
		fmt.Printf("clickhouse create table failed: %v\n", err)
		os.Exit(1)
	}
	createCancel()
	fmt.Println("clickhouse table ensured")

	// Start Kafka consumer.
	consumer := kafka.NewConsumerForTopic(cfg.Kafka, cfg.Kafka.ParsedTopic)
	defer consumer.Close()

	err = consumer.Run(ctx, func(ctx context.Context, key, value []byte) (bool, error) {
		var ev model.ParsedEvent
		if err := kafka.UnmarshalJSON(value, &ev); err != nil {
			fmt.Printf("decode error: %v | payload=%s\n", err, string(value))
			return false, nil // skip malformed, do not retry
		}

		if err := insertWithRetry(ctx, client, ev); err != nil {
			fmt.Printf("clickhouse insert failed after retries: %v\n", err)
			return false, err // do not commit so Kafka will redeliver
		}

		fmt.Printf("stored [%s] %s\n", ev.Format, ev.Source)
		return true, nil
	})

	if err != nil && err != context.Canceled {
		fmt.Printf("sink exited: %v\n", err)
		os.Exit(1)
	}
}

// insertWithRetry attempts ClickHouse insert with exponential backoff.
func insertWithRetry(ctx context.Context, client *ch.Client, ev model.ParsedEvent) error {
	backoffs := []time.Duration{100 * time.Millisecond, 250 * time.Millisecond, 500 * time.Millisecond, 1 * time.Second, 2 * time.Second}

	var lastErr error
	for i, d := range backoffs {
		if err := client.Insert(ctx, ev); err == nil {
			return nil
		} else {
			lastErr = err
			fmt.Printf("insert attempt %d failed: %v (retrying in %v)\n", i+1, err, d)
		}

		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(d):
		}
	}
	return fmt.Errorf("all retries exhausted: %w", lastErr)
}
