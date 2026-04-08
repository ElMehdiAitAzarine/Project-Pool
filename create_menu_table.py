import pymysql as mysql
import os

try:
    conn = mysql.connect(
        db="CueClubDB",
        user="root",         # Update with your user
        password="",         # Update with your password
        host="127.0.0.1",
        port=3306
    )
    cur = conn.cursor()

    # Create menu table (MariaDB/MySQL syntax)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS menu (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        price DECIMAL(10, 2) NOT NULL,
        category VARCHAR(100) NOT NULL,
        image_path TEXT,
        is_available BOOLEAN DEFAULT TRUE,
        popularity INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed some initial items if empty
    cur.execute("SELECT COUNT(*) FROM menu;")
    if cur.fetchone()[0] == 0:
        cur.execute("""
        INSERT INTO menu (name, description, price, category) VALUES
        ('Espresso', 'Pure concentrated coffee bean essence', 15.00, 'Coffee'),
        ('Cappuccino', 'Steamed milk with a thick layer of foam', 25.00, 'Coffee'),
        ('Mint Tea', 'Traditional Moroccan green tea with fresh mint', 20.00, 'Tea'),
        ('Iced Latte', 'Cold brewed espresso with chilled milk', 30.00, 'Cold'),
        ('Club Sandwich', 'Classic turkey and cheese sandwich', 45.00, 'Snacks');
        """)

    conn.commit()
    print("Menu table created and seeded successfully!")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
