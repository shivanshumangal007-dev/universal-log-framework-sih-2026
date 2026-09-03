package utils

import (
	"fmt"
	"log"
	"os"
)

// Logger is a thin wrapper around stdlib log.
type Logger struct {
	prefix string
	out    *log.Logger
}

// NewLogger creates a Logger.
func NewLogger(prefix string) *Logger {
	return &Logger{
		prefix: prefix,
		out:    log.New(os.Stdout, fmt.Sprintf("[%s] ", prefix), log.LstdFlags|log.Lmicroseconds),
	}
}

// Info logs an info message.
func (l *Logger) Info(msg string, args ...interface{}) {
	l.out.Printf("[INFO] "+msg, args...)
}

// Error logs an error message.
func (l *Logger) Error(msg string, args ...interface{}) {
	l.out.Printf("[ERROR] "+msg, args...)
}
