import os
import pandas as pd
import sqlite3
from actualizar_futbol import get_mapped_name

def process_new_season():
    # File mapping
    files_to_leagues = {
        'E0_26-27.csv': ('Premier League', 39),
        'SP1_26-27.csv': ('La Liga', 140),
        'I1_26-27.csv': ('Serie A', 135),
        'F1_26-27.csv': ('Ligue 1', 61)
    }

    raw_data_dir = 'datos_crudos'
    db_path = 'DB-Fut-Beis.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    total_inserted = 0
    total_relegated = 0
    total_promoted = 0

    for file_name, (league_name, league_id) in files_to_leagues.items():
        file_path = os.path.join(raw_data_dir, file_name)
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue

        print(f"--- Procesando {league_name} ({file_name}) ---")
        df = pd.read_csv(file_path)

        # 1. Update teams (ascenso/descenso)
        # Get unique teams from CSV
        unique_teams_csv = set(df['HomeTeam'].unique()).union(set(df['AwayTeam'].unique()))
        # Map them using the existing function to avoid duplicates
        active_teams = {get_mapped_name(t, league_id) for t in unique_teams_csv}
        
        # Get existing teams in the DB for this league
        cursor.execute("SELECT Equipo_ID, Nombre FROM futbol_equipos WHERE Liga = ?", (league_name,))
        db_teams = {row[1]: row[0] for row in cursor.fetchall()}
        
        # Teams to relegate (in DB but not in CSV)
        relegated_teams = set(db_teams.keys()) - active_teams
        for t in relegated_teams:
            cursor.execute("UPDATE futbol_equipos SET Liga = ? WHERE Nombre = ?", (f"{league_name} (Descendido)", t))
            print(f"Descendido (movido de liga): {t}")
            total_relegated += 1
            
        # Teams to promote/add (in CSV but not in DB for this league)
        for t in active_teams:
            if t not in db_teams:
                # Check if it exists in another league (e.g. previously relegated)
                cursor.execute("SELECT Equipo_ID FROM futbol_equipos WHERE Nombre = ?", (t,))
                res = cursor.fetchone()
                if res:
                    cursor.execute("UPDATE futbol_equipos SET Liga = ? WHERE Nombre = ?", (league_name, t))
                    print(f"Ascendido (actualizado a liga actual): {t}")
                else:
                    cursor.execute("INSERT INTO futbol_equipos (Nombre, Liga) VALUES (?, ?)", (t, league_name))
                    print(f"Nuevo equipo agregado: {t}")
                total_promoted += 1

        # Re-fetch teams mapping for inserting matches
        cursor.execute("SELECT Equipo_ID, Nombre FROM futbol_equipos WHERE Liga = ?", (league_name,))
        db_teams_map = {row[1]: row[0] for row in cursor.fetchall()}

        # 2. Insert matches and stats
        inserted_matches = 0
        for index, row in df.iterrows():
            # Sometimes dates are in different formats, usually DD/MM/YYYY
            date_str = str(row['Date'])
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts[2]) == 2:
                    parts[2] = "20" + parts[2]
                date_str = f"{parts[2]}-{parts[1]}-{parts[0]}"
            
            home_team = get_mapped_name(str(row['HomeTeam']), league_id)
            away_team = get_mapped_name(str(row['AwayTeam']), league_id)
            
            home_id = db_teams_map.get(home_team)
            away_id = db_teams_map.get(away_team)
            
            if not home_id or not away_id:
                print(f"Warning: Team ID missing for {home_team} or {away_team}")
                continue

            # Check if match already exists
            cursor.execute("SELECT Partido_ID FROM futbol_partidos WHERE Fecha = ? AND Local_ID = ? AND Visitante_ID = ?", (date_str, home_id, away_id))
            if cursor.fetchone():
                continue

            # Check if FTHG is nan (match postponed)
            if pd.isna(row['FTHG']):
                continue

            hg = int(row['FTHG'])
            ag = int(row['FTAG'])
            cuota_local = float(row['B365H']) if 'B365H' in df.columns and pd.notnull(row['B365H']) else 0.0
            cuota_empate = float(row['B365D']) if 'B365D' in df.columns and pd.notnull(row['B365D']) else 0.0
            cuota_visitante = float(row['B365A']) if 'B365A' in df.columns and pd.notnull(row['B365A']) else 0.0

            cursor.execute("""
                INSERT INTO futbol_partidos (Fecha, Temporada, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante, Cuota_Local, Cuota_Empate, Cuota_Visitante)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (date_str, '2026', home_id, away_id, hg, ag, cuota_local, cuota_empate, cuota_visitante))
            partido_id = cursor.lastrowid
            inserted_matches += 1

            # Insert stats if available
            def get_stat(col):
                return int(row[col]) if col in df.columns and pd.notnull(row[col]) else 0

            # Home stats
            cursor.execute("""
                INSERT INTO futbol_estadisticas (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, 0.0)
            """, (partido_id, home_id, get_stat('HS'), get_stat('HST'), get_stat('HF'), get_stat('HC'), get_stat('HY'), get_stat('HR')))
            
            # Away stats
            cursor.execute("""
                INSERT INTO futbol_estadisticas (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?, 0.0)
            """, (partido_id, away_id, get_stat('AS'), get_stat('AST'), get_stat('AF'), get_stat('AC'), get_stat('AY'), get_stat('AR')))

        print(f"Partidos insertados: {inserted_matches}")
        total_inserted += inserted_matches

    conn.commit()
    conn.close()
    
    print("--------------------------------------------------")
    print(f"Proceso finalizado. Total equipos descendidos: {total_relegated}, Ascendidos/Nuevos: {total_promoted}, Partidos insertados: {total_inserted}")

if __name__ == "__main__":
    process_new_season()
