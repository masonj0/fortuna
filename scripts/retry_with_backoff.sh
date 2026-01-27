#!/bin/bash
# scripts/retry_with_backoff.sh
# Retries a command with exponential backoff.
# Usage: ./retry_with_backoff.sh <command> <args>

MAX_ATTEMPTS=3
ATTEMPT=1
DELAY=2

while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
  echo "🚀 Attempt $ATTEMPT/$MAX_ATTEMPTS: $@"
  "$@"
  EXIT_CODE=$?

  if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Command succeeded on attempt $ATTEMPT"
    exit 0
  fi

  if [ $ATTEMPT -lt $MAX_ATTEMPTS ]; then
    echo "⚠️ Command failed with exit code $EXIT_CODE. Retrying in ${DELAY}s..."
    sleep $DELAY
    DELAY=$((DELAY * 2))
  fi

  ATTEMPT=$((ATTEMPT + 1))
done

echo "❌ Command failed after $MAX_ATTEMPTS attempts."
exit $EXIT_CODE
