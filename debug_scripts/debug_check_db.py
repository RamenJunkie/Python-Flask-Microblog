import sqlite3

conn = sqlite3.connect('microblog.db')
c = conn.cursor()

# Check what settings exist
c.execute('SELECT * FROM settings')
print("Current settings:")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]}")

conn.close()
