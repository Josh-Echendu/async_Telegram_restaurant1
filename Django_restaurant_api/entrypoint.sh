#!/bin/bash
set -e

until pg_isready -h "$DB_HOST" -U "$DB_USER"; do
  echo "Waiting for Postgres..."
  sleep 2
done

echo "Running migrations..."
python manage.py makemigrations
python manage.py migrate

echo "Starting server..."
exec python manage.py runserver 0.0.0.0:8000