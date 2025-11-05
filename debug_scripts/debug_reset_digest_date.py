import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('microblog.db')
c = conn.cursor()

# Set last digest date to 7 days ago
week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('last_digest_date', week_ago))

conn.commit()
conn.close()

print(f"Last digest date set to: {week_ago}")
