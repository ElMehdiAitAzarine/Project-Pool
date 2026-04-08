import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_project.settings')
django.setup()

from api.models import Client

def debug_db():
    clients = Client.objects.all()
    print("--- DATABASE CLIENTS ---")
    for c in clients:
        print(f"ID: {c.id} | Name: {c.full_name_cl} | Phone: {c.email_cl} | DeviceID: {c.device_id}")
    print("-------------------------")

if __name__ == "__main__":
    debug_db()
