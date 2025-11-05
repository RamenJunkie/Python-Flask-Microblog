import sqlite3

conn = sqlite3.connect('microblog.db')
c = conn.cursor()

# Add default settings
c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('site_name', 'My Blog'))
c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('social_links', ''))

conn.commit()
conn.close()
