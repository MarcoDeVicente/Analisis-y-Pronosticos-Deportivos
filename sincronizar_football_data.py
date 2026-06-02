import requests
import sqlite3
import os
import time
from actualizar_futbol import update_football_data_credits

API_TOKEN = "3a01fe1b661f4e28a99e9c9b65f3186c"
DB_PATH = os.path.join(os.path.dirname(__file__), 'DB-Fut-Beis.db')

# Mapping between football-data.org competition codes and DB League names
LEAGUE_MAPPING = {
    "PL": "Premier League",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
    "PD": "La Liga",
    "SA": "Serie A",
    "CL": "Champions League",
    "WC": "Futbol" # World Cup is represented as "Futbol" in DB teams
}

def init_db():
    print(f"Inicializando base de datos en {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create futbol_standings if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS futbol_standings (
            Standings_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Liga TEXT NOT NULL,
            Temporada TEXT NOT NULL,
            Posicion INTEGER NOT NULL,
            Equipo_Nombre TEXT NOT NULL,
            Puntos INTEGER NOT NULL,
            Jugados INTEGER NOT NULL,
            Ganados INTEGER NOT NULL,
            Empatados INTEGER NOT NULL,
            Perdidos INTEGER NOT NULL,
            Goles_Favor INTEGER NOT NULL,
            Goles_Contra INTEGER NOT NULL,
            Diferencia_Goles INTEGER NOT NULL,
            UNIQUE(Liga, Temporada, Equipo_Nombre)
        )
    ''')
    conn.commit()
    conn.close()

def clean_team_name(name, league_code=None):
    name = name.strip()
    
    # Remove common suffixes/prefixes
    suffixes = [" FC", " CF", " SD", " UD", " CD", " RC", " AC", " SSC", " AS", " SV", " SpVgg", " BSC", " TSG", " 04"]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
        if name.startswith(suffix):
            name = name[len(suffix):].strip()
            
    # Explicit overrides for standard database compatibility
    overrides = {
        "Manchester City": "Manchester City",
        "Manchester United": "Manchester United",
        "Tottenham Hotspur": "Tottenham",
        "Paris Saint-Germain": "Paris Saint-Germain",
        "FC Bayern München": "Bayern Munich",
        "Bayer 04 Leverkusen": "Leverkusen",
        "Borussia VfL 1900 Mönchengladbach": "Gladbach",
        "Mönchengladbach": "Gladbach",
        "Real Madrid CF": "Real Madrid",
        "Real Madrid": "Real Madrid",
        "FC Barcelona": "Barcelona",
        "Club Atlético de Madrid": "Atletico Madrid",
        "Atlético Madrid": "Atletico Madrid",
        "Club Atletico de Madrid": "Atletico Madrid",
        "Real Sociedad de Fútbol": "Real Sociedad",
        "Real Sociedad": "Real Sociedad",
        "Real Betis Balompié": "Real Betis",
        "Real Betis": "Real Betis",
        "Sevilla FC": "Sevilla",
        "Valencia CF": "Valencia",
        "Athletic Club": "Athletic Bilbao",
        "Inter Milan": "Inter",
        "FC Internazionale Milano": "Inter",
        "Juventus": "Juventus",
        "AC Milan": "Milan",
        "Milan": "Milan",
        "SSC Napoli": "Napoli",
        "Napoli": "Napoli",
        "AS Roma": "Roma",
        "Roma": "Roma",
        "SS Lazio": "Lazio",
        "Lazio": "Lazio",
        "Olympique de Marseille": "Marseille",
        "Olympique Lyonnais": "Lyon",
        "Lyon": "Lyon",
        "Marseille": "Marseille",
        "Monaco": "Monaco",
        "AS Monaco": "Monaco",
        "OSC Lille": "Lille",
        "Lille OSC": "Lille",
        "Lille": "Lille",
        "Stade Rennais FC 1901": "Rennes",
        "Stade Rennais": "Rennes",
        "OGC Nice": "Nice",
        "Nice": "Nice",
    }
    
    if name in overrides:
        name = overrides[name]
        
    # Match specific league naming conventions in original CSVs
    if league_code == "PL":
        if name in ("Manchester City", "Man City"):
            return "Man City"
        if name in ("Manchester United", "Man United"):
            return "Man United"
        if name in ("Newcastle United", "Newcastle"):
            return "Newcastle"
        if name in ("Tottenham Hotspur", "Tottenham"):
            return "Tottenham"
        if name in ("Nottingham Forest", "Nottingham"):
            return "Nott'm Forest"
        if name in ("Wolverhampton Wanderers", "Wolves", "Wolverhampton"):
            return "Wolves"
        if name in ("Brighton & Hove Albion", "Brighton"):
            return "Brighton"
        if name in ("West Ham United", "West Ham"):
            return "West Ham"
    elif league_code == "FL1": # Ligue 1
        if name in ("Paris Saint-Germain", "Paris Saint Germain", "PSG", "Paris SG"):
            return "Paris SG"
    elif league_code == "CL": # Champions League
        if name in ("Man City", "Manchester City"):
            return "Manchester City"
        if name in ("Man United", "Manchester United"):
            return "Manchester United"
        if name in ("Paris SG", "Paris Saint-Germain", "Paris Saint Germain", "PSG"):
            return "Paris Saint-Germain"
        if name in ("Newcastle", "Newcastle United"):
            return "Newcastle United"
            
    return name

def get_or_create_team(cursor, team_name, db_league_name):
    cursor.execute("SELECT Equipo_ID FROM futbol_equipos WHERE Nombre = ?", (team_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    
    cursor.execute("INSERT INTO futbol_equipos (Nombre, Liga) VALUES (?, ?)", (team_name, db_league_name))
    return cursor.lastrowid

def api_request(url, headers):
    print(f"Consultando URL de football-data.org: {url}")
    # Rate limit sleep BEFORE the request to strictly guarantee spacing
    time.sleep(6.5)
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        update_football_data_credits(response.headers)
        if response.status_code == 429:
            print("¡Alerta de Rate Limit (429)! Esperando 30 segundos...")
            time.sleep(30)
            response = requests.get(url, headers=headers, timeout=15)
            update_football_data_credits(response.headers)
            
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error en la petición API: {e}")
        return None

def sincronizar_liga(league_code, season, token=API_TOKEN):
    db_league_name = LEAGUE_MAPPING.get(league_code)
    if not db_league_name:
        print(f"Liga {league_code} no mapeada en la BD.")
        return {"status": "error", "message": f"Liga {league_code} no configurada."}
        
    headers = {"X-Auth-Token": token}
    
    # 1. Fetch Standings
    standings_url = f"https://api.football-data.org/v4/competitions/{league_code}/standings?season={season}"
    standings_data = api_request(standings_url, headers)
    
    # 2. Fetch Matches
    matches_url = f"https://api.football-data.org/v4/competitions/{league_code}/matches?season={season}"
    matches_data = api_request(matches_url, headers)
    
    if not standings_data and not matches_data:
        return {"status": "error", "message": f"No se pudo descargar datos para {league_code} en la temporada {season}."}
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    teams_added = 0
    matches_added = 0
    matches_skipped = 0
    standings_records = 0
    
    try:
        # --- A. PROCESAR STANDINGS ---
        if standings_data and "standings" in standings_data:
            print(f"Procesando tablas de posiciones de {db_league_name} ({season})...")
            # Clear old standings for this league and season to avoid duplicate updates
            cursor.execute("DELETE FROM futbol_standings WHERE Liga = ? AND Temporada = ?", (db_league_name, str(season)))
            
            for standings_item in standings_data["standings"]:
                # Only process TOTAL standings to avoid duplicates (HOME/AWAY)
                if standings_item.get("type") != "TOTAL":
                    continue
                table = standings_item.get("table", [])
                for row in table:
                    raw_team_name = row["team"]["name"]
                    cleaned_name = clean_team_name(raw_team_name, league_code)
                    
                    # Ensure team is in futbol_equipos
                    get_or_create_team(cursor, cleaned_name, db_league_name)
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO futbol_standings 
                        (Liga, Temporada, Posicion, Equipo_Nombre, Puntos, Jugados, Ganados, Empatados, Perdidos, Goles_Favor, Goles_Contra, Diferencia_Goles)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        db_league_name,
                        str(season),
                        row["position"],
                        cleaned_name,
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
            print(f"Guardadas {standings_records} filas de tabla de posiciones.")
            
        # --- B. PROCESAR PARTIDOS Y ESTADÍSTICAS ---
        if matches_data and "matches" in matches_data:
            print(f"Procesando partidos finalizados de {db_league_name} ({season})...")
            for match in matches_data["matches"]:
                if match.get("status") != "FINISHED":
                    continue
                    
                raw_home = match["homeTeam"]["name"]
                raw_away = match["awayTeam"]["name"]
                
                home_name = clean_team_name(raw_home, league_code)
                away_name = clean_team_name(raw_away, league_code)
                
                # Fetch or create team IDs
                local_id = get_or_create_team(cursor, home_name, db_league_name)
                visit_id = get_or_create_team(cursor, away_name, db_league_name)
                
                match_date = match["utcDate"][:10] # YYYY-MM-DD
                
                # Check duplicate match
                cursor.execute('''
                    SELECT Partido_ID FROM futbol_partidos 
                    WHERE Fecha = ? AND Local_ID = ? AND Visitante_ID = ?
                ''', (match_date, local_id, visit_id))
                if cursor.fetchone():
                    matches_skipped += 1
                    continue
                    
                goles_l = match["score"]["fullTime"]["home"]
                goles_v = match["score"]["fullTime"]["away"]
                
                if goles_l is None or goles_v is None:
                    continue
                    
                # Insert Match
                cursor.execute('''
                    INSERT INTO futbol_partidos 
                    (Fecha, Temporada, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (match_date, str(season), local_id, visit_id, goles_l, goles_v))
                
                partido_id = cursor.lastrowid
                matches_added += 1
                
                # Insert default stats (zeros) for stats and xG
                cursor.execute('''
                    INSERT INTO futbol_estadisticas 
                    (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                    VALUES (?, ?, 1, 0, 0, 0, 0, 0, 0, 0.0)
                ''', (partido_id, local_id))
                
                cursor.execute('''
                    INSERT INTO futbol_estadisticas 
                    (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                    VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0.0)
                ''', (partido_id, visit_id))
                
            conn.commit()
            print(f"Guardados {matches_added} partidos nuevos. Omitidos {matches_skipped} duplicados.")
            
        return {
            "status": "success",
            "standings_records": standings_records,
            "matches_added": matches_added,
            "matches_skipped": matches_skipped
        }
        
    except Exception as e:
        conn.rollback()
        print(f"Error en BD al guardar liga {league_code}: {e}")
        return {"status": "error", "message": f"Error de BD: {str(e)}"}
    finally:
        conn.close()

def sincronizar_todo(token=API_TOKEN):
    print("Iniciando sincronización completa de fútbol con football-data.org...")
    init_db()
    
    # Configuration of leagues and seasons
    leagues_config = [
        {"code": "PL", "seasons": [2024, 2025]},
        {"code": "BL1", "seasons": [2024, 2025]},
        {"code": "FL1", "seasons": [2024, 2025]},
        {"code": "PD", "seasons": [2024, 2025]},
        {"code": "SA", "seasons": [2024, 2025]},
        {"code": "CL", "seasons": [2024, 2025]},
        {"code": "WC", "seasons": [2022]}  # World Cup 2022
    ]
    
    resultados_totales = {
        "status": "success",
        "standings_records": 0,
        "matches_added": 0,
        "matches_skipped": 0,
        "detalles": []
    }
    
    for config in leagues_config:
        code = config["code"]
        for season in config["seasons"]:
            print(f"\n--- Sincronizando {code} (Temporada {season}) ---")
            res = sincronizar_liga(code, season, token)
            
            if res.get("status") == "success":
                resultados_totales["standings_records"] += res["standings_records"]
                resultados_totales["matches_added"] += res["matches_added"]
                resultados_totales["matches_skipped"] += res["matches_skipped"]
                resultados_totales["detalles"].append({
                    "liga": code,
                    "temporada": season,
                    "resultado": "OK",
                    "partidos": res["matches_added"],
                    "posiciones": res["standings_records"]
                })
            else:
                resultados_totales["detalles"].append({
                    "liga": code,
                    "temporada": season,
                    "resultado": "ERROR",
                    "mensaje": res.get("message")
                })
                
    print("\n¡Sincronización completa finalizada!")
    print(resultados_totales)
    return resultados_totales

if __name__ == '__main__':
    sincronizar_todo()
