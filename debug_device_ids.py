import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_project.settings')
django.setup()

from api.models import Client
from django.db import connection

def debug_device_ids():
    with connection.cursor() as cursor:
        cursor.execute("SELECT id_client, device_id FROM client")
        rows = cursor.fetchall()
        print("--- DATABASE DEVICE IDs ---")
        for row in rows:
            id_cl, dev_id = row
            if dev_id:
                print(f"ID: {id_cl} | DeviceID: '{dev_id}' | Length: {len(dev_id)} | repr: {repr(dev_id)}")
            else:
                print(f"ID: {id_cl} | DeviceID: NULL")
        print("---------------------------")

if __name__ == "__main__":
    debug_device_ids()
