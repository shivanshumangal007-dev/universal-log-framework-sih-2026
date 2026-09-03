package model

import "time"

// RawEvent is what collectors emit to the raw-logs topic.
type RawEvent struct {
	Source    string            `json:"source"` // e.g. "filetail:/var/log/app.log" or "syslog:0.0.0.0:514"
	RawLine   string            `json:"raw_line"`
	Timestamp time.Time         `json:"timestamp"`
	Metadata  map[string]string `json:"metadata,omitempty"`
}

// ParsedEvent is what parsers emit to the parsed-logs topic.
type ParsedEvent struct {
	Source      string                 `json:"source"`
	RawLine     string                 `json:"raw_line"`
	Timestamp   time.Time              `json:"timestamp"`
	Format      string                 `json:"format"` // "syslog", "json", "csv", "cef", "unknown"
	Fields      map[string]interface{} `json:"fields"` // extracted structured fields
	ParserError string                 `json:"parser_error,omitempty"`
	Metadata    map[string]string      `json:"metadata,omitempty"`
}
