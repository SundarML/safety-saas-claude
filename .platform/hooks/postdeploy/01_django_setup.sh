#!/bin/bash
set -e

# Activate the EB virtualenv (find it dynamically)
VENV=$(find /var/app/venv -name activate | head -1)
source "$VENV"

cd /var/app/current

echo "Running migrate..."
python manage.py migrate --noinput

echo "Running collectstatic..."
python manage.py collectstatic --noinput

echo "Django setup complete."
