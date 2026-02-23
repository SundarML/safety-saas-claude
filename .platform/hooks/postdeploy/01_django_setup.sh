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

echo "Creating superuser if not exists..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='admin@example.com').exists():
    User.objects.create_superuser('admin@example.com', 'Admin@1234')
    print('Superuser created.')
else:
    print('Superuser already exists.')
"

echo "Django setup complete."
