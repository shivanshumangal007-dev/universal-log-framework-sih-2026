package syslog

import (
	"context"
	"fmt"
	"net"
	"strings"
	"time"

	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/config"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/kafka"
	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/model"
)

// Collector listens on UDP for syslog messages.
type Collector struct {
	cfg      config.Syslog
	producer *kafka.Producer
}

// NewCollector creates a syslog UDP collector.
func NewCollector(cfg config.Syslog, producer *kafka.Producer) *Collector {
	return &Collector{cfg: cfg, producer: producer}
}

// Run starts the UDP listener until ctx is cancelled.
func (c *Collector) Run(ctx context.Context) error {
	addr, err := net.ResolveUDPAddr("udp", c.cfg.BindAddr)
	if err != nil {
		return fmt.Errorf("resolve udp addr: %w", err)
	}

	conn, err := net.ListenUDP("udp", addr)
	if err != nil {
		return fmt.Errorf("listen udp: %w", err)
	}
	defer conn.Close()

	fmt.Printf("syslog collector listening on %s\n", c.cfg.BindAddr)

	buf := make([]byte, c.cfg.BufferKB*1024)
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		conn.SetReadDeadline(time.Now().Add(time.Second))
		n, clientAddr, err := conn.ReadFromUDP(buf)
		if err != nil {
			if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
				continue
			}
			return fmt.Errorf("read udp: %w", err)
		}

		msg := strings.TrimSpace(string(buf[:n]))
		ev := model.RawEvent{
			Source:    fmt.Sprintf("syslog:%s", c.cfg.BindAddr),
			RawLine:   msg,
			Timestamp: time.Now().UTC(),
			Metadata: map[string]string{
				"client_ip": clientAddr.String(),
			},
		}
		if err := c.producer.Publish(ctx, "syslog", ev); err != nil {
			fmt.Printf("publish error: %v\n", err)
		}
	}
}
