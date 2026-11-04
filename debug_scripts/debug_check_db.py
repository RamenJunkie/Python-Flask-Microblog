import sqlite3

SENSITIVE = ('password', 'token', 'api_key')

conn = sqlite3.connect('microblog.db')
c = conn.cursor()

# Check what settings exist
c.execute('SELECT * FROM settings')
print("Current settings:")
for key, value in c.fetchall():
    shown = '********' if any(s in key for s in SENSITIVE) and value else value
    print(f"  {key}: {shown}")

conn.close()
