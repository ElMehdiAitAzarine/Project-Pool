import pymysql as mysql
import os

try:
    conn = mysql.connect(
        db='CueClubDB',
        user='root',         # Update to your MariaDB user
        password='',         # Update to your MariaDB password
        host='127.0.0.1',
        port=3306
    )
    cur = conn.cursor()
    cur.execute("SHOW TABLES") 
    tables = cur.fetchall()
    print("Tables in database:")
    for t in tables:
        print(f" - {t[0]}")
    
    # Check columns for command
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='command'")
    cols = cur.fetchall()
    print("\nColumns in 'command':")
    for c in cols:
        print(f" - {c[0]}")

    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
