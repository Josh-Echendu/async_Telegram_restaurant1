#!/bin/bash
set -e

# Wait for Postgres
until pg_isready -h "$DB_HOST" -U "$DB_USER"; do
  echo "Waiting for Postgres..."
  sleep 2
done

echo "Running migrations..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

echo "Starting Django server..."
python manage.py runserver 0.0.0.0:8000