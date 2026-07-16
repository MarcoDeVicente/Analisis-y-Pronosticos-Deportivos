import sqlite3

conn = sqlite3.connect("DB-Fut-Beis.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM futbol_equipos WHERE Nombre LIKE '%Arsenal%'")
rows = cursor.fetchall()
print(f"Total rows found: {len(rows)}")
for r in rows:
    print(dict(r))

conn.close()
