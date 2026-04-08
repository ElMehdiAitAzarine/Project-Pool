import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_project.settings')
django.setup()

def inspect():
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info(daily_game_session);")
        columns = cursor.fetchall()
        for col in columns:
            print(col)
            
        cursor.execute("SELECT * FROM daily_game_session;")
        rows = cursor.fetchall()
        print("\nAll Sessions:")
        for row in rows:
            print(row)

if __name__ == "__main__":
    inspect()
