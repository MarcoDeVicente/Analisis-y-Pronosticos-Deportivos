import sqlite3
conn = sqlite3.connect('DB-Fut-Beis.db')
cursor = conn.cursor()
cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name IN ("futbol_equipos", "futbol_partidos")')
for row in cursor.fetchall():
    print(row[0])
