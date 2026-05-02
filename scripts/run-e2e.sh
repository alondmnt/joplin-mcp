#!/usr/bin/env bash
set -euo pipefail

# Run E2E tests against a real Joplin instance in Docker.
# Usage: ./scripts/run-e2e.sh [pytest args...]
# Example: ./scripts/run-e2e.sh -k "test_create" -v

COMPOSE_FILE="docker-compose.e2e.yml"
cd "$(dirname "$0")/.."

# Generate Joplin config if missing (gitignored)
JOPLIN_CONFIG="tests/e2e/joplin-config.json"
if [ ! -f "$JOPLIN_CONFIG" ]; then
    echo "==> Generating $JOPLIN_CONFIG..."
    mkdir -p "$(dirname "$JOPLIN_CONFIG")"
    cat > "$JOPLIN_CONFIG" <<-JSON
	{"api.token": "e2e_test_token", "api.port": 80}
	JSON
fi

echo "==> Tearing down any leftover containers..."
docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true

echo "==> Building and starting Joplin..."
docker compose -f "$COMPOSE_FILE" up -d --build joplin

echo "==> Waiting for Joplin to be healthy..."
for i in $(seq 1 60); do
    if docker compose -f "$COMPOSE_FILE" exec -T joplin curl -sf http://localhost:80/ping >/dev/null 2>&1; then
        echo "    Joplin ready after ${i}s"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "    ERROR: Joplin not ready after 60s"
        docker compose -f "$COMPOSE_FILE" logs joplin
        docker compose -f "$COMPOSE_FILE" down -v
        exit 1
    fi
    sleep 1
done

echo "==> Running E2E tests..."
set +e
docker compose -f "$COMPOSE_FILE" run --build --rm e2e-tests pytest tests/e2e/ -v -m e2e --no-header --override-ini="addopts=" --no-cov "$@"
rc=$?
set -e

echo "==> Tearing down containers..."
docker compose -f "$COMPOSE_FILE" down -v

exit $rc
