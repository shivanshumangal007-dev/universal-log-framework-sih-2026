.PHONY: all build collector parser sink fmt vet test clean docker-build run-local

BINARY_DIR=./bin
COLLECTOR_BIN=$(BINARY_DIR)/collector
PARSER_BIN=$(BINARY_DIR)/parser
SINK_BIN=$(BINARY_DIR)/sink

all: build

build: collector parser sink

collector:
	@echo "Building collector..."
	go build -o $(COLLECTOR_BIN) ./cmd/collector

parser:
	@echo "Building parser..."
	go build -o $(PARSER_BIN) ./cmd/parser

sink:
	@echo "Building sink..."
	go build -o $(SINK_BIN) ./cmd/sink

fmt:
	go fmt ./...

vet:
	go vet ./...

test:
	go test -v ./...

clean:
	rm -rf $(BINARY_DIR)

docker-build:
	@echo "Building Docker images..."
	docker build -t log-collector:latest -f deployments/Dockerfile.collector .
	docker build -t log-parser:latest -f deployments/Dockerfile.parser .

run-local: build
	@echo "Starting Kafka via Docker Compose..."
	cd ../infra && docker compose up -d kafka
	@echo "Waiting for Kafka to be ready..."
	@sleep 5
	@echo "Run collector:  $(COLLECTOR_BIN)"
	@echo "Run parser:     $(PARSER_BIN)"
