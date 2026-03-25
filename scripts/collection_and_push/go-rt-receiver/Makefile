BINARY ?= rt-receiver
OUTPUT ?= ../$(BINARY)

.PHONY: build build-amd64 build-arm64 fmt clean

build: build-amd64

build-amd64:
	CGO_ENABLED=1 GOOS=linux GOARCH=amd64 go build -o $(OUTPUT) .

build-arm64:
	CGO_ENABLED=1 GOOS=linux GOARCH=arm64 go build -o $(OUTPUT)-arm64 .

fmt:
	gofmt -w *.go

clean:
	rm -f ../rt-receiver ../rt-receiver-arm64
