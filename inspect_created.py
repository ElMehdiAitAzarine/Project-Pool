import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_project.settings')
django.setup()

def inspect():
    with connection.cursor() as cursor:
        cursor.execute("SELECT session_id, created_at FROM daily_game_session;")
        rows = cursor.fetchall()
        for row in rows:
            print(row)

if __name__ == "__main__":
    inspect()
