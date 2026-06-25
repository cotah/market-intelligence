#!/bin/bash
set -e
echo "=== Starting entrypoint ==="
echo "=== Running alembic migrations ==="
uv run --no-sync alembic upgrade head
echo "=== Migrations done ==="
echo "=== Starting uvicorn on port ${PORT:-8000} ==="
exec uv run --no-sync uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
