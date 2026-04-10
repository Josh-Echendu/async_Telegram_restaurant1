#!/bin/bash
set -e

# Wait for Postgres
until pg_isready -h "$DB_HOST" -U "$DB_USER"; do
  echo "Waiting for Postgres..."
  sleep 2
done

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting Celery worker..."
exec celery -A restaurant_api worker --loglevel=info --concurrency=5 --max-tasks-per-child=100