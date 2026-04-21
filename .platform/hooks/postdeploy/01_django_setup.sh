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

echo "Creating initial plans if not exists..."
python manage.py shell -c "
from core.models import Plan
Plan.objects.get_or_create(name='Trial',      defaults={'max_users': 3,    'max_observations': 50,    'price_monthly': 2})
Plan.objects.get_or_create(name='Free',       defaults={'max_users': 3,    'max_observations': 20,    'price_monthly': 0})
Plan.objects.get_or_create(name='Starter',    defaults={'max_users': 25,   'max_observations': 2500,  'price_monthly': 1999})
Plan.objects.get_or_create(name='Pro',        defaults={'max_users': 50,   'max_observations': 5000,  'price_monthly': 4999})
Plan.objects.get_or_create(name='Enterprise', defaults={'max_users': None, 'max_observations': 10000, 'price_monthly': 10000})
print('Plans ready.')
"

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
