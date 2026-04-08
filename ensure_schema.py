import pymysql as mysql
import os

def ensure_schema():
    try:
        conn = mysql.connect(
            db='CueClubDB',
            user='root',         # Update to your MariaDB user
            password='',         # Update to your MariaDB password
            host='127.0.0.1',
            port=3306
        )
        conn.autocommit(True)
        cur = conn.cursor()

        print("Checking/Updating schema...")

        # 1. Add waiter_id column to command if it doesn't exist
        try:
            cur.execute("ALTER TABLE command ADD COLUMN IF NOT EXISTS waiter_id INTEGER REFERENCES waiter(id);")
            print(" - Checked 'waiter_id' column in 'command' table.")
        except Exception as e:
            print(f" - Error adding waiter_id: {e}")

        # 2. Add current_load and role to waiter
        try:
            cur.execute("ALTER TABLE waiter ADD COLUMN IF NOT EXISTS current_load INTEGER DEFAULT 0;")
            cur.execute("ALTER TABLE waiter ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'waiter';")
            print(" - Checked 'current_load' and 'role' columns in 'waiter' table.")
        except Exception as e:
            print(f" - Error adding columns to waiter: {e}")

        # 3. Create financial_record table
        try:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS financial_record (
                id INT AUTO_INCREMENT PRIMARY KEY,
                command_id INTEGER UNIQUE REFERENCES command(id_command),
                amount DECIMAL(10,2) NOT NULL,
                record_type VARCHAR(50) DEFAULT 'revenue',
                payment_method VARCHAR(50) DEFAULT 'cash',
                status VARCHAR(50) DEFAULT 'cleared',
                comptable_note TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            print(" - Checked 'financial_record' table.")
        except Exception as e:
            print(f" - Error creating financial_record table: {e}")

        cur.close()
        conn.close()
        print("Schema update completed successfully.")
    except Exception as e:
        print(f"Global Error: {e}")

if __name__ == "__main__":
    ensure_schema()
