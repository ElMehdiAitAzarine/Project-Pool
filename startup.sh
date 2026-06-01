#!/bin/bash
# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Start Gunicorn server
echo "Starting Gunicorn server..."
exec gunicorn --bind 0.0.0.0:8000 core_project.wsgi:application
