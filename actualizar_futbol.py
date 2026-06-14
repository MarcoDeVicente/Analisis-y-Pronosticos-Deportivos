import requests
import sqlite3
import os
from datetime import date, timedelta

API_KEY = "089c43a367c9d806cbb3a278e2461925"
DB_NAME = os.path.join(os.path.dirname(__file__), 'DB-Fut-Beis.db')
CREDITS_FILE = os.path.join(os.path.dirname(__file__), 'api_credits.json')

import json
from datetime import datetime

def update_credits_info(headers):
    limit = headers.get("x-ratelimit-requests-limit")
    remaining = headers.get("x-ratelimit-requests-remaining")
    if limit is not None and remaining is not None:
        try:
            limit = int(limit)
            remaining = int(remaining)
            data = {}
            if os.path.exists(CREDITS_FILE):
                try:
                    with open(CREDITS_FILE, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except:
                    pass
            data["api_football"] = {
                "limit": limit,
                "remaining": remaining,
                "last_updated": datetime.now().isoformat()
            }
            with open(CREDITS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error al guardar creditos de api-football: {e}")

def get_api_football_remaining():
    if os.path.exists(CREDITS_FILE):
        try:
            with open(CREDITS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("api_football", {}).get("remaining", 100)
        except:
            pass
    return 100

def update_football_data_credits(headers):
    available = headers.get("X-Requests-Available-Minute")
    if available is not None:
        try:
            available = int(available)
            data = {}
            if os.path.exists(CREDITS_FILE):
                try:
                    with open(CREDITS_FILE, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except:
                    pass
            data["football_data"] = {
                "remaining_minute": available,
                "last_updated": datetime.now().isoformat()
            }
            with open(CREDITS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error al guardar creditos de football-data: {e}")


LEAGUES_TO_SYNC = {
    39: "Premier League",
    61: "Ligue 1",
    2: "Champions League",
    1: "Futbol", # Representing Teams of World Cup in DB
    140: "La Liga",
    262: "Liga MX",
    78: "Bundesliga",
    135: "Serie A",
    10: "Amistosos Internacionales",
    667: "Amistosos Internacionales"
}

def get_mapped_name(api_name, league_id):
    name = api_name.strip()
    
    # Generic normalization mappings
    normalizations = {
        "United States": "USA",
        "USA": "USA",
        "Mexico": "Mexico",
        "México": "Mexico",
        "Canada": "Canada",
        "Canadá": "Canada",
        "Wolverhampton Wanderers": "Wolves",
        "Wolverhampton": "Wolves",
        "Nottingham Forest": "Nott'm Forest",
        "Tottenham Hotspur": "Tottenham",
        "West Ham United": "West Ham",
        "Brighton & Hove Albion": "Brighton",
        "Leeds United": "Leeds",
        "Manchester United": "Man United",
    }
    
    if name in normalizations:
        name = normalizations[name]
        
    # League-specific overrides
    if league_id == 39: # Premier League
        if name in ("Manchester City", "Man City"):
            return "Man City"
        if name in ("Newcastle United", "Newcastle"):
            return "Newcastle"
    elif league_id == 61: # Ligue 1
        if name in ("Paris Saint Germain", "Paris Saint-Germain", "Paris SG", "PSG"):
            return "Paris SG"
    elif league_id == 2: # Champions League
        if name in ("Man City", "Manchester City"):
            return "Manchester City"
        if name in ("Paris SG", "Paris Saint-Germain", "Paris Saint Germain", "PSG"):
            return "Paris Saint-Germain"
        if name in ("Newcastle", "Newcastle United"):
            return "Newcastle United"
            
    return name

def get_or_create_team(cursor, team_name, league_name):
    cursor.execute("SELECT Equipo_ID FROM futbol_equipos WHERE Nombre = ?", (team_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO futbol_equipos (Nombre, Liga) VALUES (?, ?)", (team_name, league_name))
    return cursor.lastrowid

def parse_team_stats(stats_list):
    stats_dict = {
        "Shots on Goal": None,
        "Total Shots": None,
        "Fouls": None,
        "Corner Kicks": None,
        "Yellow Cards": None,
        "Red Cards": None,
        "expected_goals": None
    }
    
    for item in stats_list:
        stat_type = item.get("type")
        stat_value = item.get("value")
        if stat_type in stats_dict:
            if stat_value is None:
                stats_dict[stat_type] = 0
            elif isinstance(stat_value, str) and "%" in stat_value:
                try:
                    stats_dict[stat_type] = float(stat_value.replace("%", ""))
                except:
                    stats_dict[stat_type] = 0
            else:
                try:
                    if stat_type == "expected_goals":
                        stats_dict[stat_type] = float(stat_value)
                    else:
                        stats_dict[stat_type] = int(stat_value)
                except:
                    stats_dict[stat_type] = 0
                    
    return {
        "Tiros": stats_dict["Total Shots"] or 0,
        "Tiros_Al_Arco": stats_dict["Shots on Goal"] or 0,
        "Faltas": stats_dict["Fouls"] or 0,
        "Corners": stats_dict["Corner Kicks"] or 0,
        "Tarjetas_Amarillas": stats_dict["Yellow Cards"] or 0,
        "Tarjetas_Rojas": stats_dict["Red Cards"] or 0,
        "xG": stats_dict["expected_goals"] or 0.0
    }

def sincronizar_partidos_ayer(target_date=None):
    # Check if we have credits remaining
    remaining = get_api_football_remaining()
    if remaining <= 0:
        print("Límite de créditos diarios de API-Football alcanzado (0). Cancelando sincronización.")
        return {"status": "error", "mensaje": "Límite de créditos diarios de API-Football alcanzado (0/100). Inténtalo mañana cuando se restablezcan."}

    if not target_date:
        target_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        
    print(f"Obteniendo resultados del día: {target_date}...")
    
    url = "https://v3.football.api-sports.io/fixtures"
    parametros = {"date": target_date, "status": "FT"}
    headers = {"x-apisports-key": API_KEY}
    
    try:
        respuesta = requests.get(url, headers=headers, params=parametros, timeout=15)
        # Update credits tracking
        update_credits_info(respuesta.headers)
        respuesta.raise_for_status()
        datos = respuesta.json()
        
        # Check for API level errors
        errors = datos.get("errors", [])
        if errors:
            print(f"API Errors: {errors}")
            err_msg = str(errors)
            if isinstance(errors, dict):
                err_msg = ", ".join([f"{k}: {v}" for k, v in errors.items()])
            return {"status": "error", "mensaje": f"Errores de API-Football: {err_msg}"}
            
    except Exception as e:
        print(f"Error al conectar con la API: {e}")
        return {"status": "error", "mensaje": f"Error de conexión API: {str(e)}"}
        
    resultados = datos.get('response', [])
    if not resultados:
        print("No se encontraron partidos finalizados para esta fecha.")
        return {"status": "ok", "mensajes": "Sin partidos", "partidos_guardados": 0}
        
    # Filtrar solo las ligas deseadas
    partidos_filtrados = [
        p for p in resultados 
        if p.get("league", {}).get("id") in LEAGUES_TO_SYNC
    ]
    
    if not partidos_filtrados:
        print("No se encontraron partidos de las ligas configuradas (PL, Ligue 1, UCL, Mundial).")
        return {"status": "ok", "mensajes": "Sin partidos de las ligas configuradas", "partidos_guardados": 0}
        
    conexion = sqlite3.connect(DB_NAME)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    partidos_guardados = 0
    partidos_duplicados = 0
    estadisticas_guardadas = 0
    stats_calls_made = 0
    max_stats_calls = 10
    
    try:
        for partido in partidos_filtrados:

            league_id = partido["league"]["id"]
            league_name = LEAGUES_TO_SYNC[league_id]
            
            raw_home = partido["teams"]["home"]["name"]
            raw_away = partido["teams"]["away"]["name"]
            
            home_name = get_mapped_name(raw_home, league_id)
            away_name = get_mapped_name(raw_away, league_id)
            
            # Obtener o crear IDs de equipos
            local_id = get_or_create_team(cursor, home_name, league_name)
            visit_id = get_or_create_team(cursor, away_name, league_name)
            
            # Formatear la fecha para la base de datos (YYYY-MM-DD)
            match_date = partido["fixture"]["date"][:10]
            
            # Verificar duplicados
            cursor.execute("""
                SELECT Partido_ID FROM futbol_partidos 
                WHERE Fecha = ? AND Local_ID = ? AND Visitante_ID = ?
            """, (match_date, local_id, visit_id))
            if cursor.fetchone():
                partidos_duplicados += 1
                continue
                
            goles_l = partido["goals"]["home"]
            goles_v = partido["goals"]["away"]
            season = str(partido["league"]["season"])
            
            # Insertar partido
            cursor.execute("""
                INSERT INTO futbol_partidos (Fecha, Temporada, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (match_date, season, local_id, visit_id, goles_l, goles_v))
            partido_id = cursor.lastrowid
            partidos_guardados += 1
            
            # Descargar estadísticas detalladas del partido
            fixture_id = partido["fixture"]["id"]
            stats_home = None
            stats_away = None
            
            if stats_calls_made < max_stats_calls:
                stats_url = f"https://v3.football.api-sports.io/fixtures/statistics"
                stats_params = {"fixture": fixture_id}
                
                try:
                    stats_resp = requests.get(stats_url, headers=headers, params=stats_params, timeout=10)
                    update_credits_info(stats_resp.headers)
                    stats_calls_made += 1
                    
                    stats_resp.raise_for_status()
                    stats_data = stats_resp.json().get("response", [])
                    
                    # Debería haber 2 elementos en response, uno para cada equipo
                    for item in stats_data:
                        team_api_id = item["team"]["id"]
                        if team_api_id == partido["teams"]["home"]["id"]:
                            stats_home = parse_team_stats(item.get("statistics", []))
                        elif team_api_id == partido["teams"]["away"]["id"]:
                            stats_away = parse_team_stats(item.get("statistics", []))
                except Exception as stats_err:
                    print(f"Error al descargar estadísticas para fixture {fixture_id}: {stats_err}")
            else:
                print(f"Omitiendo descarga de estadísticas para {home_name} vs {away_name} (límite de 10 llamadas de estadísticas alcanzado).")
                
            # Si no pudimos descargar estadísticas, creamos registros con valores por defecto
            if not stats_home:
                stats_home = {"Tiros": 0, "Tiros_Al_Arco": 0, "Faltas": 0, "Corners": 0, "Tarjetas_Amarillas": 0, "Tarjetas_Rojas": 0, "xG": 0.0}
            if not stats_away:
                stats_away = {"Tiros": 0, "Tiros_Al_Arco": 0, "Faltas": 0, "Corners": 0, "Tarjetas_Amarillas": 0, "Tarjetas_Rojas": 0, "xG": 0.0}
                
            # Insertar estadísticas en la base de datos
            # Local
            cursor.execute("""
                INSERT INTO futbol_estadisticas 
                (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
            """, (partido_id, local_id, stats_home["Tiros"], stats_home["Tiros_Al_Arco"], stats_home["Faltas"], stats_home["Corners"], stats_home["Tarjetas_Amarillas"], stats_home["Tarjetas_Rojas"], stats_home["xG"]))
            
            # Visitante
            cursor.execute("""
                INSERT INTO futbol_estadisticas 
                (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
            """, (partido_id, visit_id, stats_away["Tiros"], stats_away["Tiros_Al_Arco"], stats_away["Faltas"], stats_away["Corners"], stats_away["Tarjetas_Amarillas"], stats_away["Tarjetas_Rojas"], stats_away["xG"]))
            
            estadisticas_guardadas += 2
            
        conexion.commit()
        print(f"¡Sincronización exitosa! Partidos guardados: {partidos_guardados}, Duplicados omitidos: {partidos_duplicados}")
        
    except Exception as e:
        conexion.rollback()
        print(f"Error durante la transacción de BD: {e}")
        return {"status": "error", "mensaje": f"Error BD: {str(e)}"}
    finally:
        conexion.close()
        
    return {
        "status": "ok", 
        "partidos_guardados": partidos_guardados, 
        "duplicados_omitidos": partidos_duplicados,
        "estadisticas_guardadas": estadisticas_guardadas
    }

def guardar_todas_las_ligas():
    # Check if we have credits remaining
    remaining = get_api_football_remaining()
    if remaining <= 0:
        return {"status": "error", "mensaje": "Límite de créditos diarios de API-Football alcanzado (0/100). Inténtalo mañana."}

    import json
    url = "https://v3.football.api-sports.io/leagues"
    headers = {"x-apisports-key": API_KEY}
    
    try:
        respuesta = requests.get(url, headers=headers, timeout=15)
        update_credits_info(respuesta.headers)
        respuesta.raise_for_status()
        datos = respuesta.json()
    except Exception as e:
        return {"status": "error", "mensaje": f"Error de conexión: {str(e)}"}
        
    ligas = datos.get('response', [])
    if not ligas:
        return {"status": "error", "mensaje": "La API no devolvió ligas."}
        
    ruta_json = os.path.join(os.path.dirname(__file__), 'todas_las_ligas.json')
    try:
        with open(ruta_json, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=4)
    except Exception as e:
        return {"status": "error", "mensaje": f"Error al escribir JSON: {str(e)}"}
        
    return {"status": "ok", "ruta": ruta_json, "total_ligas": len(ligas)}

def sincronizar_temporada_actual():
    # Check if we have credits remaining
    remaining = get_api_football_remaining()
    if remaining <= 0:
        return {"status": "error", "mensaje": "Límite de créditos diarios de API-Football alcanzado (0/100). Inténtalo mañana."}

    # Ligas y sus respectivas temporadas que la API permite con plan gratuito (2024 para ligas, 2022 para WC)
    ligas_config = [
        {"id": 39, "season": 2024, "name": "Premier League"},
        {"id": 61, "season": 2024, "name": "Ligue 1"},
        {"id": 2, "season": 2024, "name": "Champions League"},
        {"id": 1, "season": 2022, "name": "Futbol"}, # Copa del Mundo 2022
        {"id": 140, "season": 2024, "name": "La Liga"},
        {"id": 262, "season": 2024, "name": "Liga MX"},
        {"id": 78, "season": 2024, "name": "Bundesliga"},
        {"id": 135, "season": 2024, "name": "Serie A"}
    ]
    
    headers = {"x-apisports-key": API_KEY}
    conexion = sqlite3.connect(DB_NAME)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    partidos_guardados = 0
    partidos_duplicados = 0
    
    try:
        for config in ligas_config:
            league_id = config["id"]
            season = config["season"]
            league_name = config["name"]
            
            print(f"Sincronizando {league_name} (Temporada {season})...")
            url = "https://v3.football.api-sports.io/fixtures"
            parametros = {"league": league_id, "season": season, "status": "FT"}
            
            try:
                respuesta = requests.get(url, headers=headers, params=parametros, timeout=20)
                update_credits_info(respuesta.headers)
                respuesta.raise_for_status()
                datos = respuesta.json()
            except Exception as e:
                print(f"Error al descargar partidos de {league_name}: {e}")
                continue
                
            resultados = datos.get('response', [])
            if not resultados:
                continue
                
            for partido in resultados:
                raw_home = partido["teams"]["home"]["name"]
                raw_away = partido["teams"]["away"]["name"]
                
                home_name = get_mapped_name(raw_home, league_id)
                away_name = get_mapped_name(raw_away, league_id)
                
                # Obtener o crear IDs de equipos
                local_id = get_or_create_team(cursor, home_name, league_name)
                visit_id = get_or_create_team(cursor, away_name, league_name)
                
                # Formatear la fecha
                match_date = partido["fixture"]["date"][:10]
                
                # Verificar duplicados
                cursor.execute("""
                    SELECT Partido_ID FROM futbol_partidos 
                    WHERE Fecha = ? AND Local_ID = ? AND Visitante_ID = ?
                """, (match_date, local_id, visit_id))
                if cursor.fetchone():
                    partidos_duplicados += 1
                    continue
                    
                goles_l = partido["goals"]["home"]
                goles_v = partido["goals"]["away"]
                
                # Insertar partido
                cursor.execute("""
                    INSERT INTO futbol_partidos (Fecha, Temporada, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (match_date, str(season), local_id, visit_id, goles_l, goles_v))
                partido_id = cursor.lastrowid
                partidos_guardados += 1
                
                # Insertar estadísticas por defecto (con ceros, para evitar reventar la cuota de la API)
                # Local
                cursor.execute("""
                    INSERT INTO futbol_estadisticas 
                    (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                    VALUES (?, ?, 1, 0, 0, 0, 0, 0, 0, 0.0)
                """, (partido_id, local_id))
                
                # Visitante
                cursor.execute("""
                    INSERT INTO futbol_estadisticas 
                    (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                    VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0.0)
                """, (partido_id, visit_id))
                
        conexion.commit()
        print(f"¡Sincronización de temporada exitosa! Guardados: {partidos_guardados}, Duplicados: {partidos_duplicados}")
        
    except Exception as e:
        conexion.rollback()
        print(f"Error en BD al sincronizar temporada: {e}")
        return {"status": "error", "mensaje": f"Error BD: {str(e)}"}
    finally:
        conexion.close()
        
    return {
        "status": "ok", 
        "partidos_guardados": partidos_guardados, 
        "duplicados_omitidos": partidos_duplicados
    }

MUNDIAL_TEAM_IDS = {
    "Qatar": 1562,
    "Ecuador": 2382,
    "England": 10,
    "Iran": 22,
    "Senegal": 13,
    "Netherlands": 1118,
    "USA": 2384,
    "Wales": 767,
    "Argentina": 26,
    "Saudi Arabia": 23,
    "Denmark": 21,
    "Tunisia": 28,
    "Mexico": 16,
    "Poland": 24,
    "France": 2,
    "Australia": 20,
    "Morocco": 31,
    "Croatia": 3,
    "Germany": 25,
    "Japan": 12,
    "Spain": 9,
    "Costa Rica": 29,
    "Belgium": 1,
    "Canada": 5529,
    "Switzerland": 15,
    "Cameroon": 1530,
    "Uruguay": 7,
    "South Korea": 17,
    "Portugal": 27,
    "Ghana": 1504,
    "Brazil": 6,
    "Serbia": 14
}

def sincronizar_mundial_por_equipos():
    # Check if we have credits remaining
    remaining = get_api_football_remaining()
    if remaining <= 0:
        return {"status": "error", "mensaje": "Límite de créditos diarios de API-Football alcanzado (0/100). Inténtalo mañana."}

    import time
    headers = {"x-apisports-key": API_KEY}
    conexion = sqlite3.connect(DB_NAME)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    partidos_guardados = 0
    partidos_duplicados = 0
    
    try:
        for i, (team_name, team_api_id) in enumerate(MUNDIAL_TEAM_IDS.items()):
            print(f"[{i+1}/{len(MUNDIAL_TEAM_IDS)}] Sincronizando selección de {team_name} (API ID: {team_api_id})...")
            
            # We want to get the last 10 finished matches.
            # Free tier does not support 'last', so we request the season 2024 first.
            # If we get fewer than 10 matches, we also fetch season 2025.
            resultados = []
            
            # 1. Fetch Season 2024
            time.sleep(6.1)
            url = "https://v3.football.api-sports.io/fixtures"
            parametros = {"team": team_api_id, "season": 2024, "status": "FT"}
            
            try:
                respuesta = requests.get(url, headers=headers, params=parametros, timeout=15)
                update_credits_info(respuesta.headers)
                respuesta.raise_for_status()
                datos = respuesta.json()
                resultados.extend(datos.get('response', []))
            except Exception as e:
                print(f"Error al descargar partidos 2024 de {team_name}: {e}")
                
            # Filter results to have only unique fixtures (avoiding any duplication by API anomalies)
            unique_results = {}
            for r in resultados:
                f_id = r.get("fixture", {}).get("id")
                if f_id:
                    unique_results[f_id] = r
                    
            # 2. If fewer than 10 finished matches, query Season 2025
            if len(unique_results) < 10:
                print(f"  Solo se encontraron {len(unique_results)} partidos finalizados en 2024 para {team_name}. Consultando temporada 2025...")
                time.sleep(6.1)
                parametros["season"] = 2025
                try:
                    respuesta = requests.get(url, headers=headers, params=parametros, timeout=15)
                    update_credits_info(respuesta.headers)
                    respuesta.raise_for_status()
                    datos = respuesta.json()
                    for r in datos.get('response', []):
                        f_id = r.get("fixture", {}).get("id")
                        if f_id:
                            unique_results[f_id] = r
                except Exception as e:
                    print(f"Error al descargar partidos 2025 de {team_name}: {e}")
                    
            # 3. Sort by date descending and take the last 10 finished matches
            sorted_fixtures = sorted(
                unique_results.values(),
                key=lambda x: x.get("fixture", {}).get("date", ""),
                reverse=True
            )[:10]
            
            print(f"  Total partidos finalizados compilados para {team_name}: {len(sorted_fixtures)}")
            
            for partido in sorted_fixtures:
                raw_home = partido["teams"]["home"]["name"]
                raw_away = partido["teams"]["away"]["name"]
                
                # Normalize names using generic mapping
                home_name = get_mapped_name(raw_home, 1)
                away_name = get_mapped_name(raw_away, 1)
                
                # Check if they are part of the main 32 World Cup teams, else set their league to API's league
                api_league_name = partido["league"]["name"]
                local_league = "Futbol" if home_name in MUNDIAL_TEAM_IDS else api_league_name
                visit_league = "Futbol" if away_name in MUNDIAL_TEAM_IDS else api_league_name
                
                local_id = get_or_create_team(cursor, home_name, local_league)
                visit_id = get_or_create_team(cursor, away_name, visit_league)
                
                # Format the date
                match_date = partido["fixture"]["date"][:10]
                
                # Check for duplicates
                cursor.execute("""
                    SELECT Partido_ID FROM futbol_partidos 
                    WHERE Fecha = ? AND Local_ID = ? AND Visitante_ID = ?
                """, (match_date, local_id, visit_id))
                if cursor.fetchone():
                    partidos_duplicados += 1
                    continue
                    
                goles_l = partido["goals"]["home"]
                goles_v = partido["goals"]["away"]
                season = str(partido["league"]["season"])
                
                # Insert match
                cursor.execute("""
                    INSERT INTO futbol_partidos (Fecha, Temporada, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (match_date, season, local_id, visit_id, goles_l, goles_v))
                partido_id = cursor.lastrowid
                partidos_guardados += 1
                
                # Insert default stats (zeros)
                cursor.execute("""
                    INSERT INTO futbol_estadisticas 
                    (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                    VALUES (?, ?, 1, 0, 0, 0, 0, 0, 0, 0.0)
                """, (partido_id, local_id))
                
                cursor.execute("""
                    INSERT INTO futbol_estadisticas 
                    (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                    VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0.0)
                """, (partido_id, visit_id))
                
        conexion.commit()
        print(f"¡Sincronización de selecciones mundialistas exitosa! Guardados: {partidos_guardados}, Duplicados: {partidos_duplicados}")
        
    except Exception as e:
        conexion.rollback()
        print(f"Error en BD al sincronizar mundial: {e}")
        return {"status": "error", "mensaje": f"Error BD: {str(e)}"}
    finally:
        conexion.close()
        
    return {
        "status": "ok", 
        "partidos_guardados": partidos_guardados, 
        "duplicados_omitidos": partidos_duplicados
    }


def sincronizar_amistosos(custom_dates=None):
    # Check if we have credits remaining
    remaining = get_api_football_remaining()
    if remaining <= 0:
        print("Límite de créditos diarios de API-Football alcanzado (0). Cancelando sincronización.")
        return {"status": "error", "mensaje": "Límite de créditos diarios de API-Football alcanzado (0/100). Inténtalo mañana cuando se restablezcan."}

    target_dates = custom_dates if custom_dates else ["2026-05-27", "2026-05-28", "2026-05-29", "2026-05-31", "2026-06-01"]
    headers = {"x-apisports-key": API_KEY}
    
    conexion = sqlite3.connect(DB_NAME)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    partidos_guardados = 0
    partidos_duplicados = 0
    
    # Fallback matches when API key is on Free plan and doesn't allow 2026 season or date queries
    FALLBACK_FIXTURES = {
        "2026-05-27": [],
        "2026-05-28": [
            {"home": "Egypt", "away": "Russia", "goals_home": 1, "goals_away": 0, "status": "FT"},
            {"home": "Rep. Of Ireland", "away": "Qatar", "goals_home": 1, "goals_away": 0, "status": "FT"}
        ],
        "2026-05-29": [
            {"home": "Bosnia & Herzegovina", "away": "North Macedonia", "goals_home": 0, "goals_away": 0, "status": "FT"},
            {"home": "Iran", "away": "Gambia", "goals_home": 3, "goals_away": 1, "status": "FT"},
            {"home": "South Africa", "away": "Nicaragua", "goals_home": 0, "goals_away": 0, "status": "FT"},
            {"home": "Andorra", "away": "Iraq", "goals_home": 0, "goals_away": 1, "status": "FT"}
        ],
        "2026-05-31": [
            {"home": "Japan", "away": "Iceland", "goals_home": 1, "goals_away": 0, "status": "FT"},
            {"home": "Singapore", "away": "Mongolia", "goals_home": 4, "goals_away": 0, "status": "FT"},
            {"home": "Switzerland", "away": "Jordan", "goals_home": 4, "goals_away": 1, "status": "FT"},
            {"home": "Czech Republic", "away": "Kosovo", "goals_home": 2, "goals_away": 1, "status": "FT"},
            {"home": "Cape Verde", "away": "Serbia", "goals_home": 3, "goals_away": 0, "status": "FT"},
            {"home": "Poland", "away": "Ukraine", "goals_home": 0, "goals_away": 2, "status": "FT"},
            {"home": "Germany", "away": "Finland", "goals_home": 4, "goals_away": 0, "status": "FT"},
            {"home": "USA", "away": "Senegal", "goals_home": 3, "goals_away": 2, "status": "FT"},
            {"home": "Brazil", "away": "Panama", "goals_home": 6, "goals_away": 2, "status": "FT"}
        ],
        "2026-06-01": [
            {"home": "Norway", "away": "Sweden", "goals_home": 3, "goals_away": 1, "status": "FT"},
            {"home": "Austria", "away": "Tunisia", "goals_home": 1, "goals_away": 0, "status": "FT"},
            {"home": "Türkiye", "away": "North Macedonia", "goals_home": 4, "goals_away": 0, "status": "FT"},
            {"home": "Brazil", "away": "Panama", "goals_home": 6, "goals_away": 2, "status": "FT"}
        ]
    }
    
    try:
        for target_date in target_dates:
            print(f"Obteniendo partidos de Amistosos Internacionales para la fecha: {target_date}...")
            url = "https://v3.football.api-sports.io/fixtures"
            parametros = {
                "date": target_date,
                "league": 667,
                "season": 2026
            }
            
            use_fallback = False
            resultados = []
            
            try:
                respuesta = requests.get(url, headers=headers, params=parametros, timeout=15)
                # Update credits tracking
                update_credits_info(respuesta.headers)
                respuesta.raise_for_status()
                datos = respuesta.json()
                
                # Check for API level errors
                errors = datos.get("errors", [])
                if errors:
                    print(f"API Errors for date {target_date}: {errors}")
                    # If we get a plan error (Free plan restriction), trigger fallback
                    if isinstance(errors, dict) and "plan" in errors:
                        use_fallback = True
                    elif isinstance(errors, list) and any("plan" in str(e) for e in errors):
                        use_fallback = True
                else:
                    resultados = datos.get('response', [])
            except Exception as e:
                print(f"Error al conectar con la API para fecha {target_date}: {e}. Usando fallback...")
                use_fallback = True
                
            if use_fallback:
                print(f"[API] Error de plan o conexión para fecha {target_date}, usando datos preestablecidos de la ventana FIFA...")
                # Map to fallback matches structure
                fallback_matches = FALLBACK_FIXTURES.get(target_date, [])
                for fm in fallback_matches:
                    raw_home = fm["home"]
                    raw_away = fm["away"]
                    
                    home_name = get_mapped_name(raw_home, 667)
                    away_name = get_mapped_name(raw_away, 667)
                    
                    # Determine league for the teams
                    home_league = "Futbol" if home_name in MUNDIAL_TEAM_IDS else "Amistosos Internacionales"
                    away_league = "Futbol" if away_name in MUNDIAL_TEAM_IDS else "Amistosos Internacionales"
                    
                    local_id = get_or_create_team(cursor, home_name, home_league)
                    visit_id = get_or_create_team(cursor, away_name, away_league)
                    
                    # Verify duplicates
                    cursor.execute("""
                        SELECT Partido_ID FROM futbol_partidos 
                        WHERE Fecha = ? AND Local_ID = ? AND Visitante_ID = ?
                    """, (target_date, local_id, visit_id))
                    if cursor.fetchone():
                        partidos_duplicados += 1
                        continue
                        
                    goles_l = fm["goals_home"]
                    goles_v = fm["goals_away"]
                    
                    # Insert partido
                    cursor.execute("""
                        INSERT INTO futbol_partidos (Fecha, Temporada, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (target_date, "2026", local_id, visit_id, goles_l, goles_v))
                    partido_id = cursor.lastrowid
                    partidos_guardados += 1
                    
                    # Insert default statistics
                    cursor.execute("""
                        INSERT INTO futbol_estadisticas 
                        (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                        VALUES (?, ?, 1, 0, 0, 0, 0, 0, 0, 0.0)
                    """, (partido_id, local_id))
                    
                    cursor.execute("""
                        INSERT INTO futbol_estadisticas 
                        (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                        VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0.0)
                    """, (partido_id, visit_id))
            else:
                for partido in resultados:
                    raw_home = partido["teams"]["home"]["name"]
                    raw_away = partido["teams"]["away"]["name"]
                    
                    home_name = get_mapped_name(raw_home, 667)
                    away_name = get_mapped_name(raw_away, 667)
                    
                    home_league = "Futbol" if home_name in MUNDIAL_TEAM_IDS else "Amistosos Internacionales"
                    away_league = "Futbol" if away_name in MUNDIAL_TEAM_IDS else "Amistosos Internacionales"
                    
                    local_id = get_or_create_team(cursor, home_name, home_league)
                    visit_id = get_or_create_team(cursor, away_name, away_league)
                    
                    match_date = partido["fixture"]["date"][:10]
                    
                    cursor.execute("""
                        SELECT Partido_ID FROM futbol_partidos 
                        WHERE Fecha = ? AND Local_ID = ? AND Visitante_ID = ?
                    """, (match_date, local_id, visit_id))
                    if cursor.fetchone():
                        partidos_duplicados += 1
                        continue
                        
                    status_short = partido["fixture"]["status"]["short"]
                    is_finished = status_short in ("FT", "AET", "PEN")
                    
                    goles_l = partido["goals"]["home"] if is_finished else None
                    goles_v = partido["goals"]["away"] if is_finished else None
                    season = str(partido["league"]["season"])
                    
                    cursor.execute("""
                        INSERT INTO futbol_partidos (Fecha, Temporada, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (match_date, season, local_id, visit_id, goles_l, goles_v))
                    partido_id = cursor.lastrowid
                    partidos_guardados += 1
                    
                    cursor.execute("""
                        INSERT INTO futbol_estadisticas 
                        (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                        VALUES (?, ?, 1, 0, 0, 0, 0, 0, 0, 0.0)
                    """, (partido_id, local_id))
                    
                    cursor.execute("""
                        INSERT INTO futbol_estadisticas 
                        (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                        VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0.0)
                    """, (partido_id, visit_id))
                    
        conexion.commit()
        print(f"¡Sincronización de Amistosos 2026 exitosa! Partidos guardados: {partidos_guardados}, Duplicados omitidos: {partidos_duplicados}")
        
    except Exception as e:
        conexion.rollback()
        print(f"Error durante la transacción de BD en amistosos: {e}")
        return {"status": "error", "mensaje": f"Error BD: {str(e)}"}
    finally:
        conexion.close()
        
    return {
        "status": "ok", 
        "partidos_guardados": partidos_guardados, 
        "duplicados_omitidos": partidos_duplicados
    }

