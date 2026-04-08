import hashlib
from datetime import date
import qrcode
from io import BytesIO
import base64
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env so FRONTEND_URL is available (works whether called via Django or directly)
load_dotenv(Path(__file__).resolve().parent / '.env')


def generate_daily_token():
    """Generates a stable, daily token based on the current date."""
    today = str(date.today())
    salt = "CUECLUB_SALT_2024"
    return hashlib.sha256((today + salt).encode()).hexdigest()


def generate_qr_image():
    """Generates and saves the QR code PNG to the server directory."""
    token = generate_daily_token()
    frontend_url = os.environ.get('FRONTEND_URL', 'http://192.168.1.42:3000')
    qr_data = f"{frontend_url}/verify?token={token}"

    print(f"QR points to: {qr_data}")

    qr = qrcode.QRCode(version=1, box_size=10, border=0)
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    today = str(date.today())
    save_dir = os.path.join(os.path.dirname(__file__), "uploads", "qrcodes")
    os.makedirs(save_dir, exist_ok=True)
    
    file_name = f"daily_qr_{today}.png"
    file_path = os.path.join(save_dir, file_name)

    img.save(file_path, format="PNG")
    
    return f"qrcodes/{file_name}"
