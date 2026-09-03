package clickhouse

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/model"
)

func TestEventIDDeterministic(t *testing.T) {
	ev := model.ParsedEvent{
		Source:    "filetail:/var/log/app.log",
		RawLine:   "test line",
		Timestamp: time.Date(2026, 9, 4, 12, 0, 0, 0, time.UTC),
		Format:    "json",
		Fields:    map[string]interface{}{"level": "info"},
		Metadata:  map[string]string{"host": "srv1"},
	}

	id1 := EventID(ev)
	id2 := EventID(ev)
	if id1 != id2 {
		t.Fatalf("event_id not deterministic: %s != %s", id1, id2)
	}
	if len(id1) != 32 {
		t.Fatalf("expected id length 32, got %d", len(id1))
	}

	// Different event should produce different ID.
	ev2 := ev
	ev2.RawLine = "different line"
	id3 := EventID(ev2)
	if id1 == id3 {
		t.Fatal("different event produced same event_id")
	}
}

func TestEventIDWithNilMaps(t *testing.T) {
	ev := model.ParsedEvent{
		Source:    "syslog:0.0.0.0:514",
		RawLine:   "<34>Oct 11 22:14:15 h msg",
		Timestamp: time.Now().UTC(),
		Format:    "syslog",
	}
	id1 := EventID(ev)
	id2 := EventID(ev)
	if id1 != id2 {
		t.Fatalf("event_id not deterministic with nil maps: %s != %s", id1, id2)
	}
}

func TestSerializeParsedEvent(t *testing.T) {
	ev := model.ParsedEvent{
		Source:    "test",
		RawLine:   `{"a":1}`,
		Timestamp: time.Date(2026, 9, 4, 12, 0, 0, 0, time.UTC),
		Format:    "json",
		Fields:    map[string]interface{}{"a": float64(1)},
		Metadata:  map[string]string{"k": "v"},
	}

	fieldsJSON, err := json.Marshal(ev.Fields)
	if err != nil {
		t.Fatalf("marshal fields: %v", err)
	}
	metaJSON, err := json.Marshal(ev.Metadata)
	if err != nil {
		t.Fatalf("marshal metadata: %v", err)
	}

	var f map[string]interface{}
	if err := json.Unmarshal(fieldsJSON, &f); err != nil {
		t.Fatalf("unmarshal fields: %v", err)
	}
	if f["a"] != float64(1) {
		t.Fatalf("expected a=1, got %v", f["a"])
	}

	var m map[string]string
	if err := json.Unmarshal(metaJSON, &m); err != nil {
		t.Fatalf("unmarshal metadata: %v", err)
	}
	if m["k"] != "v" {
		t.Fatalf("expected k=v, got %v", m["k"])
	}
}
