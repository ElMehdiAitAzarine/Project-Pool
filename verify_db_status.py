import pymysql as mysql

def verify_db():
    try:
        conn = mysql.connect(
            db="CueClubDB",
            user="root",         # Update with your user
            password="",         # Update with your password
            host="127.0.0.1",
            port=3306
        )
        cur = conn.cursor()

        tables = ['menu', 'waiter', 'command']
        for table in tables:
            print(f"\n--- Checking table: {table} ---")
            try:
                cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}';")
                columns = cur.fetchall()
                if not columns:
                    print(f"Table '{table}' NOT FOUND!")
                for col in columns:
                    print(f"Column: {col[0]} ({col[1]})")
            except Exception as e:
                print(f"Error checking {table}: {e}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    verify_db()
