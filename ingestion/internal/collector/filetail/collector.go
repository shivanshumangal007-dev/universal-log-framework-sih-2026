package filetail

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"time"

	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/config"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/kafka"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/model"
)

// Collector tails files and publishes RawEvents to Kafka.
type Collector struct {
	cfg      config.FileTail
	producer *kafka.Producer
}

// NewCollector creates a file-tail collector.
func NewCollector(cfg config.FileTail, producer *kafka.Producer) *Collector {
	return &Collector{cfg: cfg, producer: producer}
}

// Run starts tailing all configured files until ctx is cancelled.
func (c *Collector) Run(ctx context.Context) error {
	for _, path := range c.cfg.Paths {
		go c.tailFile(ctx, path)
	}
	<-ctx.Done()
	return ctx.Err()
}

func (c *Collector) tailFile(ctx context.Context, path string) {
	ticker := time.NewTicker(c.cfg.PollInterval)
	defer ticker.Stop()

	var offset int64
	warnedMissing := false

	if c.cfg.StartAtEnd {
		info, err := os.Stat(path)
		if err == nil {
			offset = info.Size()
		}
	}

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if _, err := os.Stat(path); err != nil {
				if !warnedMissing {
					fmt.Printf("filetail warning %s: file not found, waiting...\n", path)
					warnedMissing = true
				}
				continue
			}
			warnedMissing = false

			newOffset, err := c.readLines(ctx, path, offset)
			if err != nil {
				fmt.Printf("filetail error %s: %v\n", path, err)
				continue
			}
			offset = newOffset
		}
	}
}

func (c *Collector) readLines(ctx context.Context, path string, offset int64) (int64, error) {
	f, err := os.Open(path)
	if err != nil {
		return offset, err
	}
	defer f.Close()

	stat, err := f.Stat()
	if err != nil {
		return offset, err
	}
	if stat.Size() < offset {
		// File was truncated; restart from beginning.
		offset = 0
	}

	if _, err := f.Seek(offset, 0); err != nil {
		return offset, err
	}

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		ev := model.RawEvent{
			Source:    fmt.Sprintf("filetail:%s", path),
			RawLine:   line,
			Timestamp: time.Now().UTC(),
		}
		if err := c.producer.Publish(ctx, path, ev); err != nil {
			fmt.Printf("publish error: %v\n", err)
		}
	}
	if err := scanner.Err(); err != nil {
		return offset, err
	}

	newOffset, err := f.Seek(0, 1)
	if err != nil {
		return offset, err
	}
	return newOffset, nil
}
