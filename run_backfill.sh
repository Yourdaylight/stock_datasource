#!/bin/bash
# Script to run backfill with correct environment variables

# Load .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run backfill command
uv run python cli.py backfill "$@"
