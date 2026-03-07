#!/bin/bash
while true; do
  H=$(curl -s http://127.0.0.1:8000/health || echo "fail")
  if [[ "$H" != *"ok"* ]]; then
    curl -s -X POST http://127.0.0.1:7000/control/distributed-brain -H "Content-Type: application/json" -d "{\"action\":\"start\"}" >/dev/null || true
  fi
  sleep 10
done
