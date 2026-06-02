import requests
import sqlite3
import csv
import os
import time
from actualizar_futbol import update_football_data_credits

API_TOKEN = "3a01fe1b661f4e28a99e9c9b65f3186c"
DB_PATH = os.path.join(os.path.dirname(__file__), 'DB-Fut-Beis.db')

def normalize_name(name):
    if not name:
        return ""
    name = name.strip()
    # Handle unicode encoding characters for Curacao
    name = name.replace("Curaçao", "Curacao").replace("Curaao", "Curacao").replace("Cura\u00e7ao", "Curacao")
    
    mappings = {
        "United States": "USA",
        "Czechia": "Czech Republic",
        "Bosnia-Herzegovina": "Bosnia & Herzegovina",
        "Bosnia and Herzegovina": "Bosnia & Herzegovina",
        "Congo DR": "D.R. Congo",
        "DR Congo": "D.R. Congo",
        "Cape Verde Islands": "Cape Verde",
        "Cabo Verde": "Cape Verde"
    }
    return mappings.get(name, name)

def get_or_create_team(cursor, name, league="Futbol"):
    cursor.execute("SELECT Equipo_ID FROM futbol_equipos WHERE Nombre = ?", (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO futbol_equipos (Nombre, Liga) VALUES (?, ?)", (name, league))
    return cursor.lastrowid

def to_int(val, default=0):
    try:
        if not val or val.strip() == "":
            return default
        return int(float(val))
    except:
        return default

def to_float(val, default=0.0):
    try:
        if not val or val.strip() == "":
            return default
        return float(val)
    except:
        return default

def api_request(url, headers):
    print(f"Consultando API de football-data.org: {url}")
    # Force 6.5s delay to strictly comply with the 10 calls/min rate limit
    time.sleep(6.5)
    try:
        response = requests.get(url, headers=headers, timeout=15)
        update_football_data_credits(response.headers)
        if response.status_code == 429:
            print("Rate limit superado. Esperando 30 segundos...")
            time.sleep(30)
            response = requests.get(url, headers=headers, timeout=15)
            update_football_data_credits(response.headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error en llamada API: {e}")
        return None

def sincronizar_mundial_2026(token=API_TOKEN):
    print("Iniciando sincronización del Mundial 2026...")
    headers = {"X-Auth-Token": token}
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    teams_created = 0
    standings_records = 0
    matches_added = 0
    matches_skipped = 0
    
    try:
        # 1. Fetch World Cup Teams from football-data.org
        teams_url = "https://api.football-data.org/v4/competitions/WC/teams"
        teams_data = api_request(teams_url, headers)
        if teams_data and "teams" in teams_data:
            print(f"Encontrados {len(teams_data['teams'])} equipos oficiales en la API...")
            for t in teams_data["teams"]:
                normalized = normalize_name(t["name"])
                # We need to see if we created a new team
                cursor.execute("SELECT Equipo_ID FROM futbol_equipos WHERE Nombre = ?", (normalized,))
                if not cursor.fetchone():
                    get_or_create_team(cursor, normalized, "Futbol")
                    teams_created += 1
            conn.commit()
            print(f"Registrados {teams_created} equipos nuevos de la API.")
        
        # 2. Fetch Standings from football-data.org
        standings_url = "https://api.football-data.org/v4/competitions/WC/standings?season=2026"
        standings_data = api_request(standings_url, headers)
        if standings_data and "standings" in standings_data:
            print("Actualizando tabla de posiciones del Mundial 2026...")
            cursor.execute("DELETE FROM futbol_standings WHERE Liga = 'Futbol' AND Temporada = '2026'")
            
            for standing in standings_data["standings"]:
                if standing.get("type") != "TOTAL":
                    continue
                for row in standing.get("table", []):
                    normalized = normalize_name(row["team"]["name"])
                    get_or_create_team(cursor, normalized, "Futbol") # double check team exists
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO futbol_standings 
                        (Liga, Temporada, Posicion, Equipo_Nombre, Puntos, Jugados, Ganados, Empatados, Perdidos, Goles_Favor, Goles_Contra, Diferencia_Goles)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        "Futbol",
                        "2026",
                        row["position"],
                        normalized,
                        row["points"],
                        row["playedGames"],
                        row["won"],
                        row["draw"],
                        row["lost"],
                        row["goalsFor"],
                        row["goalsAgainst"],
                        row["goalDifference"]
                    ))
                    standings_records += 1
            conn.commit()
            print(f"Guardadas {standings_records} filas en la tabla de posiciones.")
            
        # 3. Load Matches from Local CSV Files
        csv_files = [
            {"path": os.path.join(os.path.dirname(__file__), "WorldCup2026-1.csv"), "has_fouls": True},
            {"path": os.path.join(os.path.dirname(__file__), "anfitriones_stats_real.csv"), "has_fouls": False}
        ]
        
        for csv_config in csv_files:
            csv_path = csv_config["path"]
            has_fouls = csv_config["has_fouls"]
            
            if not os.path.exists(csv_path):
                print(f"Archivo CSV no encontrado: {csv_path}. Omitiendo.")
                continue
                
            print(f"Ingestando partidos desde: {os.path.basename(csv_path)}...")
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    home_name = normalize_name(row["Home"])
                    away_name = normalize_name(row["Away"])
                    match_date = row["Date"].strip() # YYYY-MM-DD
                    
                    # Get or create team IDs
                    local_id = get_or_create_team(cursor, home_name, "Futbol")
                    visit_id = get_or_create_team(cursor, away_name, "Futbol")
                    
                    # Duplicate check
                    cursor.execute('''
                        SELECT Partido_ID FROM futbol_partidos 
                        WHERE Fecha = ? AND Local_ID = ? AND Visitante_ID = ?
                    ''', (match_date, local_id, visit_id))
                    
                    if cursor.fetchone():
                        matches_skipped += 1
                        continue
                        
                    goles_l = to_int(row["HG"])
                    goles_v = to_int(row["AG"])
                    
                    # Insert Match
                    cursor.execute('''
                        INSERT INTO futbol_partidos (Fecha, Temporada, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (match_date, "2026", local_id, visit_id, goles_l, goles_v))
                    
                    partido_id = cursor.lastrowid
                    matches_added += 1
                    
                    # Ingest stats
                    local_stats = {
                        "Tiros": to_int(row.get("HS")),
                        "Tiros_Al_Arco": to_int(row.get("HST")),
                        "Faltas": to_int(row.get("HF")) if has_fouls else 0,
                        "Corners": to_int(row.get("HC")),
                        "Tarjetas_Amarillas": to_int(row.get("HY")),
                        "Tarjetas_Rojas": to_int(row.get("HR")),
                        "xG": to_float(row.get("HxG"))
                    }
                    
                    visit_stats = {
                        "Tiros": to_int(row.get("AS")),
                        "Tiros_Al_Arco": to_int(row.get("AST")),
                        "Faltas": to_int(row.get("AF")) if has_fouls else 0,
                        "Corners": to_int(row.get("AC")),
                        "Tarjetas_Amarillas": to_int(row.get("AY")),
                        "Tarjetas_Rojas": to_int(row.get("AR")),
                        "xG": to_float(row.get("AxG"))
                    }
                    
                    # Insert Local Stats
                    cursor.execute('''
                        INSERT INTO futbol_estadisticas 
                        (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                        VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        partido_id, local_id, 
                        local_stats["Tiros"], local_stats["Tiros_Al_Arco"], local_stats["Faltas"],
                        local_stats["Corners"], local_stats["Tarjetas_Amarillas"], local_stats["Tarjetas_Rojas"],
                        local_stats["xG"]
                    ))
                    
                    # Insert Visitor Stats
                    cursor.execute('''
                        INSERT INTO futbol_estadisticas 
                        (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                        VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        partido_id, visit_id, 
                        visit_stats["Tiros"], visit_stats["Tiros_Al_Arco"], visit_stats["Faltas"],
                        visit_stats["Corners"], visit_stats["Tarjetas_Amarillas"], visit_stats["Tarjetas_Rojas"],
                        visit_stats["xG"]
                    ))
            conn.commit()
            print(f"Ingesta de {os.path.basename(csv_path)} finalizada.")
            
        print("Sincronización del Mundial 2026 completada con éxito.")
        return {
            "status": "success",
            "teams_created": teams_created,
            "standings_records": standings_records,
            "matches_added": matches_added,
            "matches_skipped": matches_skipped
        }
    except Exception as e:
        conn.rollback()
        print(f"Error de base de datos durante sincronización del mundial: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
    finally:
        conn.close()

if __name__ == '__main__':
    res = sincronizar_mundial_2026()
    print(res)
