import sqlite3

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        code TEXT,
        verified INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

def add_user(name, email, password, code):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (name, email, password, code) VALUES (?, ?, ?, ?)",
                  (name, email, password, code))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_code(email, input_code):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT code FROM users WHERE email=?", (email,))
    row = c.fetchone()
    if row and row[0] == input_code:
        c.execute("UPDATE users SET verified=1 WHERE email=?", (email,))
        conn.commit()
        return True
    return False

def is_verified(email):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT verified FROM users WHERE email=?", (email,))
    row = c.fetchone()
    return row and row[0] == 1
