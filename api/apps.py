from django.apps import AppConfig
import threading
import time
import os
import sys

def run_qr_generator():
    try:
        from qr_logic import generate_qr_image
        while True:
            try:
                generate_qr_image()
                print("QR code generated successfully.")
            except Exception as e:
                print(f"Error generating QR code: {e}")
            time.sleep(3600)  # Sleep for 1 hour
    except Exception as e:
        print(f"Failed to start QR generator: {e}")

class ApiConfig(AppConfig):
    name = 'api'

    def ready(self):
        # Prevent duplicate thread in Django development server
        if os.environ.get('RUN_MAIN', None) == 'true':
            thread = threading.Thread(target=run_qr_generator, daemon=True)
            thread.start()
