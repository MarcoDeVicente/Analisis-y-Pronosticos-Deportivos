import sqlite3

conn = sqlite3.connect("DB-Fut-Beis.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get IDs
cursor.execute("SELECT Equipo_ID, Nombre, Liga FROM futbol_equipos WHERE Nombre IN ('Arsenal', 'Paris SG')")
teams = {row["Nombre"]: (row["Equipo_ID"], row["Liga"]) for row in cursor.fetchall()}

for name, (team_id, liga) in teams.items():
    print(f"\n=== HISTORIAL PARA {name.upper()} (Liga Principal en BD: {liga}) ===")
    
    # Matches as Local
    cursor.execute("""
        SELECT fp.Fecha, fe_v.Nombre as Rival, fe_v.Liga as Liga_Rival, fp.Goles_Local, fp.Goles_Visitante
        FROM futbol_partidos fp
        JOIN futbol_equipos fe_v ON fp.Visitante_ID = fe_v.Equipo_ID
        WHERE fp.Local_ID = ?
        ORDER BY fp.Fecha DESC
    """, (team_id,))
    local_matches = cursor.fetchall()
    print(f"Partidos como Local en Base de Datos: {len(local_matches)}")
    print("Muestra de últimos 5 partidos como Local:")
    for m in local_matches[:5]:
        print(f"  {m['Fecha']}: {name} {m['Goles_Local']} - {m['Goles_Visitante']} {m['Rival']} (Rival es de Liga: {m['Liga_Rival']})")
        
    # Matches as Visitante
    cursor.execute("""
        SELECT fp.Fecha, fe_l.Nombre as Rival, fe_l.Liga as Liga_Rival, fp.Goles_Local, fp.Goles_Visitante
        FROM futbol_partidos fp
        JOIN futbol_equipos fe_l ON fp.Local_ID = fe_l.Equipo_ID
        WHERE fp.Visitante_ID = ?
        ORDER BY fp.Fecha DESC
    """, (team_id,))
    visit_matches = cursor.fetchall()
    print(f"Partidos como Visitante en Base de Datos: {len(visit_matches)}")
    print("Muestra de últimos 5 partidos como Visitante:")
    for m in visit_matches[:5]:
        print(f"  {m['Fecha']}: {m['Rival']} {m['Goles_Local']} - {m['Goles_Visitante']} {name} (Rival es de Liga: {m['Liga_Rival']})")

conn.close()
