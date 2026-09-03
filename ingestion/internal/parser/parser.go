package parser

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/shivanshumangal-dev/log-ingestion-sih/internal/model"
)

// Parser is a function that tries to parse a raw line into a ParsedEvent.
// If it returns ok=false, the next parser should be tried.
type Parser func(raw model.RawEvent) (model.ParsedEvent, bool)

// Chain tries parsers in order; the last fallback is "unknown".
func Chain(raw model.RawEvent, parsers ...Parser) model.ParsedEvent {
	for _, p := range parsers {
		if ev, ok := p(raw); ok {
			return ev
		}
	}
	// Unknown format fallback.
	return model.ParsedEvent{
		Source:    raw.Source,
		RawLine:   raw.RawLine,
		Timestamp: raw.Timestamp,
		Format:    "unknown",
		Fields:    map[string]interface{}{},
		Metadata:  raw.Metadata,
	}
}

// DefaultChain is the recommended parser order.
func DefaultChain(raw model.RawEvent) model.ParsedEvent {
	return Chain(raw, ParseJSON, ParseSyslog, ParseCEF, ParseCSV)
}

// ParseJSON attempts to parse the line as JSON.
func ParseJSON(raw model.RawEvent) (model.ParsedEvent, bool) {
	var fields map[string]interface{}
	if err := json.Unmarshal([]byte(raw.RawLine), &fields); err != nil {
		return model.ParsedEvent{}, false
	}
	return model.ParsedEvent{
		Source:    raw.Source,
		RawLine:   raw.RawLine,
		Timestamp: raw.Timestamp,
		Format:    "json",
		Fields:    fields,
		Metadata:  raw.Metadata,
	}, true
}

// syslogRegex matches RFC3164-ish syslog lines.
// Example: <34>Oct 11 22:14:15 mymachine su: 'su root' failed for lonvick on /dev/pts/8
var syslogRegex = regexp.MustCompile(`^<(\d+)>(\w+\s+\d+\s+\d+:\d+:\d+)\s+(\S+)\s+(.*)$`)

// ParseSyslog attempts RFC3164 parsing.
func ParseSyslog(raw model.RawEvent) (model.ParsedEvent, bool) {
	matches := syslogRegex.FindStringSubmatch(raw.RawLine)
	if matches == nil {
		return model.ParsedEvent{}, false
	}

	pri := matches[1]
	tsStr := matches[2]
	host := matches[3]
	msg := matches[4]

	// Extract severity and facility from priority.
	var severity, facility int
	fmt.Sscanf(pri, "%d", &severity)
	facility = severity >> 3
	severity = severity & 0x07

	ts, err := time.Parse("Jan _2 15:04:05", tsStr)
	if err != nil {
		ts = raw.Timestamp
	} else {
		// Syslog lacks year; assume current.
		ts = ts.AddDate(time.Now().Year(), 0, 0)
	}

	fields := map[string]interface{}{
		"priority":  pri,
		"facility":  facility,
		"severity":  severity,
		"hostname":  host,
		"message":   msg,
		"syslog_ts": tsStr,
	}

	return model.ParsedEvent{
		Source:    raw.Source,
		RawLine:   raw.RawLine,
		Timestamp: ts,
		Format:    "syslog",
		Fields:    fields,
		Metadata:  raw.Metadata,
	}, true
}

// cefRegex matches CEF:0|Vendor|Product|Version|... headers.
var cefRegex = regexp.MustCompile(`^CEF:(\d+)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|(.*)$`)

// ParseCEF attempts CEF header parsing.
func ParseCEF(raw model.RawEvent) (model.ParsedEvent, bool) {
	matches := cefRegex.FindStringSubmatch(raw.RawLine)
	if matches == nil {
		return model.ParsedEvent{}, false
	}

	fields := map[string]interface{}{
		"version":      matches[1],
		"vendor":       matches[2],
		"product":      matches[3],
		"version_str":  matches[4],
		"signature_id": matches[5],
		"name":         matches[6],
		"severity":     matches[7],
	}

	// Parse extensions as key=value pairs.
	extensions := matches[8]
	extMap := map[string]string{}
	for _, part := range strings.Split(extensions, " ") {
		if kv := strings.SplitN(part, "=", 2); len(kv) == 2 {
			extMap[kv[0]] = kv[1]
		}
	}
	fields["extensions"] = extMap

	return model.ParsedEvent{
		Source:    raw.Source,
		RawLine:   raw.RawLine,
		Timestamp: raw.Timestamp,
		Format:    "cef",
		Fields:    fields,
		Metadata:  raw.Metadata,
	}, true
}

// ParseCSV attempts to parse the line as CSV (requires >= 2 columns).
func ParseCSV(raw model.RawEvent) (model.ParsedEvent, bool) {
	reader := csv.NewReader(strings.NewReader(raw.RawLine))
	reader.FieldsPerRecord = -1 // allow variable fields
	records, err := reader.Read()
	if err != nil || len(records) < 2 {
		return model.ParsedEvent{}, false
	}

	fields := map[string]interface{}{}
	for i, v := range records {
		fields[fmt.Sprintf("col_%d", i)] = v
	}
	fields["columns"] = records

	return model.ParsedEvent{
		Source:    raw.Source,
		RawLine:   raw.RawLine,
		Timestamp: raw.Timestamp,
		Format:    "csv",
		Fields:    fields,
		Metadata:  raw.Metadata,
	}, true
}
