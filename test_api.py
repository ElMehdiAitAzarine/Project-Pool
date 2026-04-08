import requests
try:
    r = requests.get('http://localhost:8000/api/game-status', timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Data: {r.json()}")
except Exception as e:
    print(f"Error: {e}")
