import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_project.settings')
django.setup()

with connection.cursor() as cursor:
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    tables = cursor.fetchall()
    for table in tables:
        print(table[0])
