package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	filetail "github.com/shivanshumangal-dev/log-ingestion-sih/internal/collector/filetail"
	syslog "github.com/shivanshumangal-dev/log-ingestion-sih/internal/collector/syslog"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/config"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/kafka"
)

func main() {
	cfg := config.LoadCollector()
	fmt.Printf("collector starting | kafka=%s\n", cfg.Kafka)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sig
		fmt.Println("shutting down collector...")
		cancel()
	}()

	producer := kafka.NewProducer(cfg.Kafka, cfg.Kafka.RawTopic)
	defer producer.Close()

	// Start syslog collector.
	syslogCollector := syslog.NewCollector(cfg.Syslog, producer)
	go func() {
		if err := syslogCollector.Run(ctx); err != nil {
			fmt.Printf("syslog collector exited: %v\n", err)
		}
	}()

	// Start file-tail collector.
	fileCollector := filetail.NewCollector(cfg.FileTail, producer)
	if err := fileCollector.Run(ctx); err != nil {
		fmt.Printf("file collector exited: %v\n", err)
	}
}
