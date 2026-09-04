package parser

import (
	"testing"
	"time"

	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/model"
)

func TestParseJSON(t *testing.T) {
	raw := model.RawEvent{RawLine: `{"level":"info","msg":"hello"}`}
	p, ok := ParseJSON(raw)
	if !ok {
		t.Fatal("expected ok")
	}
	if p.Format != "json" {
		t.Fatalf("expected format json, got %s", p.Format)
	}
	if p.Fields["level"] != "info" {
		t.Fatalf("expected level=info, got %v", p.Fields["level"])
	}
}

func TestParseSyslog(t *testing.T) {
	raw := model.RawEvent{RawLine: "<34>Oct 11 22:14:15 mymachine su: failed for lonvick"}
	p, ok := ParseSyslog(raw)
	if !ok {
		t.Fatal("expected ok")
	}
	if p.Format != "syslog" {
		t.Fatalf("expected format syslog, got %s", p.Format)
	}
	if p.Fields["hostname"] != "mymachine" {
		t.Fatalf("expected hostname=mymachine, got %v", p.Fields["hostname"])
	}
}

func TestParseCEF(t *testing.T) {
	raw := model.RawEvent{RawLine: "CEF:0|Security|threatmanager|1.0|100|worm stopped|10|src=10.0.0.1 dst=10.0.0.2"}
	p, ok := ParseCEF(raw)
	if !ok {
		t.Fatal("expected ok")
	}
	if p.Format != "cef" {
		t.Fatalf("expected format cef, got %s", p.Format)
	}
	if p.Fields["vendor"] != "Security" {
		t.Fatalf("expected vendor=Security, got %v", p.Fields["vendor"])
	}
}

func TestParseCSV(t *testing.T) {
	raw := model.RawEvent{RawLine: "John,30,New York"}
	p, ok := ParseCSV(raw)
	if !ok {
		t.Fatal("expected ok")
	}
	if p.Format != "csv" {
		t.Fatalf("expected format csv, got %s", p.Format)
	}
	if p.Fields["col_0"] != "John" {
		t.Fatalf("expected col_0=John, got %v", p.Fields["col_0"])
	}
}

func TestDefaultChain(t *testing.T) {
	tests := []struct {
		line   string
		format string
	}{
		{`{"a":1}`, "json"},
		{"<34>Oct 11 22:14:15 h msg", "syslog"},
		{"CEF:0|A|B|1|2|C|10|", "cef"},
		{"a,b,c", "csv"},
	}
	for _, tc := range tests {
		raw := model.RawEvent{RawLine: tc.line, Timestamp: time.Now()}
		p, ok := DefaultChain(raw)
		if !ok {
			t.Fatalf("line=%q expected ok=true", tc.line)
		}
		if p.Format != tc.format {
			t.Fatalf("line=%q expected %s got %s", tc.line, tc.format, p.Format)
		}
	}
}

func TestDefaultChainUnknownFormat(t *testing.T) {
	raw := model.RawEvent{RawLine: "totally unrecognizable garbage", Timestamp: time.Now()}
	p, ok := DefaultChain(raw)
	if ok {
		t.Fatalf("expected ok=false for unknown format, got ok=true with format=%s", p.Format)
	}
}
