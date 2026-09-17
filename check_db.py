import sqlite3
conn = sqlite3.connect('DB-Fut-Beis.db')
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM futbol_partidos")
print("Partidos total:", cursor.fetchone()[0])
cursor.execute("SELECT COUNT(*) FROM futbol_estadisticas")
print("Estadisticas total:", cursor.fetchone()[0])

cursor.execute("SELECT Partido_ID FROM futbol_partidos ORDER BY Partido_ID DESC LIMIT 150")
recent_partidos = [r[0] for r in cursor.fetchall()]

cursor.execute(f"SELECT Partido_ID, COUNT(*) FROM futbol_estadisticas WHERE Partido_ID IN ({','.join(map(str, recent_partidos))}) GROUP BY Partido_ID HAVING COUNT(*) < 2")
missing_stats = cursor.fetchall()
print("Partidos with missing stats:", len(missing_stats))

if len(missing_stats) > 0:
    print("Example missing stats for Partido_IDs:", [m[0] for m in missing_stats[:5]])

