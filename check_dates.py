import os
import django
from django.utils import timezone
from api.models import DailyGameSession

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_project.settings')
django.setup()

def check():
    now = timezone.now()
    today = now.date()
    print(f"Server Date (UTC): {today}")
    sessions = DailyGameSession.objects.all()
    for s in sessions:
        s_date = s.created_at.date() if s.created_at else None
        print(f"Session {s.session_id}: Created {s.created_at}, Date {s_date}, Status {s.status}, Game Status {s.game_status}")
        if s_date == today:
            print("  -> Matches today's date")
        else:
            print("  -> Does NOT match today's date")

if __name__ == "__main__":
    check()
