package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/config"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/kafka"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/model"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/parser"
)

func main() {
	cfg := config.LoadParser()
	fmt.Printf("parser starting | kafka=%s\n", cfg.Kafka)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sig
		fmt.Println("shutting down parser...")
		cancel()
	}()

	producer := kafka.NewProducer(cfg.Kafka, cfg.Kafka.ParsedTopic)
	defer producer.Close()

	consumer := kafka.NewConsumer(cfg.Kafka)
	defer consumer.Close()

	err := consumer.Run(ctx, func(ctx context.Context, key, value []byte) (bool, error) {
		var raw model.RawEvent
		if err := kafka.UnmarshalJSON(value, &raw); err != nil {
			return false, fmt.Errorf("unmarshal raw event: %w", err)
		}

		parsed := parser.DefaultChain(raw)
		if err := producer.Publish(ctx, string(key), parsed); err != nil {
			return false, fmt.Errorf("publish parsed event: %w", err)
		}
		fmt.Printf("parsed [%s] -> %s\n", parsed.Format, parsed.Source)
		return true, nil
	})

	if err != nil && err != context.Canceled {
		fmt.Printf("parser exited: %v\n", err)
		os.Exit(1)
	}
}
