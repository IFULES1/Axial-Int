#!/usr/bin/env bash
# Lance le serveur Qdrant natif (port 6355, isolé de l'ancien Docker sur 6333).
# Stockage persistant dans data/qdrant-server. Logs dans data/qdrant-server.log.
set -e
cd "$(dirname "$0")/.."

if curl -s http://localhost:6355/healthz >/dev/null 2>&1; then
  echo "Qdrant déjà en marche sur http://localhost:6355"
  exit 0
fi

export QDRANT__SERVICE__HTTP_PORT=6355
export QDRANT__SERVICE__GRPC_PORT=6356
export QDRANT__STORAGE__STORAGE_PATH="$(pwd)/data/qdrant-server"
export QDRANT__TELEMETRY_DISABLED=true

nohup ./bin/qdrant > data/qdrant-server.log 2>&1 &
echo "Qdrant lancé (PID $!). Santé :"
until curl -s http://localhost:6355/healthz >/dev/null 2>&1; do sleep 1; done
curl -s http://localhost:6355/collections
echo ""
