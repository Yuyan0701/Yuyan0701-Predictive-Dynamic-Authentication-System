import sqlite3

def init_db():
    conn = sqlite3.connect('pdas.db')
    c = conn.cursor()
    
    # Drop existing table if it exists
    c.execute('''DROP TABLE IF EXISTS users''')
    
    # Create users table with all required columns
    c.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            username_email TEXT UNIQUE NOT NULL,
            country_code TEXT NOT NULL,
            phone TEXT NOT NULL,
            password TEXT NOT NULL,
            generated_password TEXT,
            password_seed TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    
if __name__ == '__main__':
    init_db()
    print("Database initialized successfully!")