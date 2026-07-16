import sqlite3

conn = sqlite3.connect("DB-Fut-Beis.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- SAMPLE UCL MATCHES ---")
cursor.execute("""
    SELECT fe_l.Nombre as Local, fe_v.Nombre as Visitante, fe_l.Liga as Liga_L, fe_v.Liga as Liga_V
    FROM futbol_partidos fp
    JOIN futbol_equipos fe_l ON fp.Local_ID = fe_l.Equipo_ID
    JOIN futbol_equipos fe_v ON fp.Visitante_ID = fe_v.Equipo_ID
    WHERE fe_l.Liga = 'Champions League' OR fe_v.Liga = 'Champions League'
    LIMIT 20
""")
for row in cursor.fetchall():
    print(f"{row['Local']} ({row['Liga_L']}) vs {row['Visitante']} ({row['Liga_V']})")

conn.close()
