#!/bin/bash
set -e

# Wait for Postgres
until pg_isready -h "$DB_HOST" -U "$DB_USER"; do
  echo "Waiting for Postgres..."
  sleep 2
done

# Ensure migrations are applied
echo "Running migrations before starting Celery..."
python manage.py migrate

# Start Celery worker
echo "Starting Celery..."
exec celery -A restaurant_api worker --loglevel=info --concurrency=5 --max-tasks-per-child=100
