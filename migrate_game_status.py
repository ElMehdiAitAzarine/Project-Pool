import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_project.settings')
django.setup()

def add_column():
    with connection.cursor() as cursor:
        try:
            cursor.execute("ALTER TABLE daily_game_session ADD COLUMN game_status VARCHAR(50) DEFAULT 'active';")
            print("Successfully added game_status column")
        except Exception as e:
            print(f"Error adding column: {e}")

if __name__ == "__main__":
    add_column()
