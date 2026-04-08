import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_project.settings')
django.setup()

with connection.cursor() as cursor:
    cursor.execute("SELECT app, name FROM django_migrations")
    migrations = cursor.fetchall()
    for app, name in migrations:
        print(f"{app}: {name}")
