#!/bin/bash
set -e

echo "=== Core API Entrypoint ==="

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until pg_isready -h postgres-core -p 5432 -U core_user; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done
echo "PostgreSQL is ready!"

# Run database migrations
echo "Running database migrations..."
if [ -d "/app/alembic" ]; then
    cd /app
    alembic upgrade head
    echo "Database migrations completed successfully"
else
    echo "No alembic directory found, skipping migrations"
fi

# Execute the main command
echo "Starting application..."
exec "$@"
