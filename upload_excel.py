import pandas as pd
import sqlite3

def upload_excel_to_db():
    df = pd.read_excel('Amistosos_Internacional_PreMundial_2026.xlsx')
    conn = sqlite3.connect('DB-Fut-Beis.db')
    cursor = conn.cursor()

    inserted_matches = 0
    teams_created = 0

    for index, row in df.iterrows():
        # Get or insert Home team
        home_team = str(row['Home']).strip()
        cursor.execute("SELECT Equipo_ID FROM futbol_equipos WHERE Nombre = ?", (home_team,))
        res = cursor.fetchone()
        if res:
            home_id = res[0]
        else:
            cursor.execute("INSERT INTO futbol_equipos (Nombre, Liga) VALUES (?, ?)", (home_team, 'Amistosos Internacionales'))
            home_id = cursor.lastrowid
            teams_created += 1

        # Get or insert Away team
        away_team = str(row['Away']).strip()
        cursor.execute("SELECT Equipo_ID FROM futbol_equipos WHERE Nombre = ?", (away_team,))
        res = cursor.fetchone()
        if res:
            away_id = res[0]
        else:
            cursor.execute("INSERT INTO futbol_equipos (Nombre, Liga) VALUES (?, ?)", (away_team, 'Amistosos Internacionales'))
            away_id = cursor.lastrowid
            teams_created += 1

        # Insert Partido
        date_str = str(row['Date'])
        # Skip if match already exists
        cursor.execute("SELECT Partido_ID FROM futbol_partidos WHERE Fecha = ? AND Local_ID = ? AND Visitante_ID = ?", (date_str, home_id, away_id))
        if cursor.fetchone():
            continue

        # Extract fields
        hg = int(row['HG'])
        ag = int(row['AG'])
        cuota_local = float(row['H_Avg']) if pd.notnull(row['H_Avg']) else 0.0
        cuota_empate = float(row['D_Avg']) if pd.notnull(row['D_Avg']) else 0.0
        cuota_visitante = float(row['A_Avg']) if pd.notnull(row['A_Avg']) else 0.0

        cursor.execute("""
            INSERT INTO futbol_partidos (Fecha, Temporada, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante, Cuota_Local, Cuota_Empate, Cuota_Visitante)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (date_str, 'Amistosos Pre-Mundial 2026', home_id, away_id, hg, ag, cuota_local, cuota_empate, cuota_visitante))
        partido_id = cursor.lastrowid
        inserted_matches += 1

        # Insert stats Home
        try:
            xg_home = float(row['HxG']) if pd.notnull(row['HxG']) else 0.0
        except:
            xg_home = 0.0
            
        cursor.execute("""
            INSERT INTO futbol_estadisticas (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (partido_id, home_id, 1, int(row['HS']), int(row['HST']), int(row['HF']), int(row['HC']), int(row['HY']), int(row['HR']), xg_home))

        # Insert stats Away
        try:
            xg_away = float(row['AxG']) if pd.notnull(row['AxG']) else 0.0
        except:
            xg_away = 0.0
            
        cursor.execute("""
            INSERT INTO futbol_estadisticas (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (partido_id, away_id, 0, int(row['AS']), int(row['AST']), int(row['AF']), int(row['AC']), int(row['AY']), int(row['AR']), xg_away))

    conn.commit()
    conn.close()
    return {"inserted_matches": inserted_matches, "teams_created": teams_created}

if __name__ == "__main__":
    res = upload_excel_to_db()
    print("Datos subidos:", res)
