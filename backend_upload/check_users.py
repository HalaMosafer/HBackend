import sqlite3

conn = sqlite3.connect('users.db')
c = conn.cursor()
c.execute("UPDATE users SET verified=1 WHERE email='raniarimawi1@gmail.com'")
conn.commit()
print("✅ verified manually.")
conn.close()
