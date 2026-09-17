import sqlite3
conn = sqlite3.connect('DB-Fut-Beis.db')
cursor = conn.cursor()
cursor.execute('SELECT Liga, COUNT(*) FROM futbol_equipos GROUP BY Liga')
for row in cursor.fetchall():
    print(row)
