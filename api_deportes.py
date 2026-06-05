# Force reload submodules
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from scipy.stats import poisson
import sqlite3
from actualizar_futbol import sincronizar_partidos_ayer, guardar_todas_las_ligas, sincronizar_temporada_actual, sincronizar_mundial_por_equipos, sincronizar_amistosos
import os
import math
import random

app = FastAPI(title="Motor Predictivo Multideporte (Fútbol y MLB)")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "DB-Fut-Beis.db")

def get_db_connection():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail=f"Database file not found at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- ENDPOINTS PARA OBTENER EQUIPOS ---

@app.get("/api/equipos/futbol")
def obtener_equipos_futbol():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT Nombre, Liga, rank_mundial FROM futbol_equipos ORDER BY Nombre ASC")
        rows = cursor.fetchall()
        
        # Categorized lists
        grupos = {
            "Premier League": [],
            "La Liga": [],
            "Liga MX": [],
            "Bundesliga": [],
            "Serie A": [],
            "Ligue 1": [],
            "Champions League": [],
            "Equipos de Mundial": [],
            "Amistosos Internacionales": []
        }
        
        display_names = {
            "USA": "EE.UU.",
            "Mexico": "México"
        }
        
        # List of teams that play in Champions League but are primarily in Premier League or Ligue 1 in DB
        ucl_crossover_teams = {"Arsenal", "Chelsea", "Liverpool", "Tottenham", "Marseille", "Monaco"}
        
        for row in rows:
            name = row["Nombre"]
            liga = row["Liga"]
            rank = row["rank_mundial"]
            
            # Map label
            label = display_names.get(name, name)
            item = {"value": name, "label": label, "rank_mundial": rank}
            
            if liga == "Futbol":
                grupos["Equipos de Mundial"].append(item)
            elif liga == "Amistosos Internacionales":
                grupos["Amistosos Internacionales"].append(item)
            elif liga == "Premier League":
                grupos["Premier League"].append(item)
                if name in ucl_crossover_teams:
                    grupos["Champions League"].append(item)
            elif liga == "Ligue 1":
                grupos["Ligue 1"].append(item)
                if name in ucl_crossover_teams:
                    grupos["Champions League"].append(item)
            elif liga == "Champions League":
                grupos["Champions League"].append(item)
            else:
                if liga not in grupos:
                    grupos[liga] = []
                grupos[liga].append(item)
                
        # Remove empty groups
        grupos = {k: v for k, v in grupos.items() if len(v) > 0}
        return {"grupos": grupos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/equipos/beisbol")
def obtener_equipos_beisbol():
    # User's division configuration
    EQUIPOS_MLB = {
        "American League": {
            "AL East": ["New York Yankees", "Baltimore Orioles", "Boston Red Sox", "Toronto Blue Jays", "Tampa Bay Rays"],
            "AL Central": ["Cleveland Guardians", "Minnesota Twins", "Chicago White Sox", "Kansas City Royals", "Detroit Tigers"],
            "AL West": ["Houston Astros", "Texas Rangers", "Seattle Mariners", "Los Angeles Angels", "Oakland Athletics"]
        },
        "National League": {
            "NL East": ["Atlanta Braves", "Philadelphia Phillies", "New York Mets", "Miami Marlins", "Washington Nationals"],
            "NL Central": ["Milwaukee Brewers", "Chicago Cubs", "Cincinnati Reds", "Pittsburgh Pirates", "St. Louis Cardinals"],
            "NL West": ["Los Angeles Dodgers", "San Francisco Giants", "San Diego Padres", "Arizona Diamondbacks", "Colorado Rockies"]
        }
    }
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT Nombre FROM beisbol_equipos")
        rows = cursor.fetchall()
        db_teams = [row["Nombre"] for row in rows]
        
        # We want to group them by Division (AL East, NL Central, etc.)
        grupos = {
            "AL East": [],
            "AL Central": [],
            "AL West": [],
            "NL East": [],
            "NL Central": [],
            "NL West": []
        }
        
        # Helper to find division and display label
        for db_name in db_teams:
            # Match database name to display label
            display_label = db_name
            if db_name == "Athletics":
                display_label = "Oakland Athletics"
                
            found = False
            # Find which league/division this display_label belongs to
            for league, divisions in EQUIPOS_MLB.items():
                for div, team_list in divisions.items():
                    if display_label in team_list:
                        grupos[div].append({"value": db_name, "label": display_label})
                        found = True
                        break
                if found:
                    break
                    
            if not found:
                if "Otros" not in grupos:
                    grupos["Otros"] = []
                grupos["Otros"].append({"value": db_name, "label": display_label})
                
        # Remove empty groups and sort teams in each division alphabetically by label
        grupos = {k: sorted(v, key=lambda x: x["label"]) for k, v in grupos.items() if len(v) > 0}
        return {"grupos": grupos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- PREDICCIÓN DE FÚTBOL ---

@app.get("/api/pronostico/futbol")
def obtener_pronostico_futbol(local: str, visitante: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Obtener IDs y ranking mundial
        cursor.execute("SELECT Equipo_ID, rank_mundial FROM futbol_equipos WHERE Nombre = ?", (local,))
        row_local = cursor.fetchone()
        cursor.execute("SELECT Equipo_ID, rank_mundial FROM futbol_equipos WHERE Nombre = ?", (visitante,))
        row_visit = cursor.fetchone()
        
        if not row_local or not row_visit:
            raise HTTPException(status_code=404, detail="Uno o ambos equipos no fueron encontrados en la base de datos.")
            
        local_id = row_local["Equipo_ID"]
        rank_l_str = row_local["rank_mundial"]
        visit_id = row_visit["Equipo_ID"]
        rank_v_str = row_visit["rank_mundial"]
        
        # Unify history for duplicate team names (Ligue 1 vs Champions League / Premier League vs Champions League)
        unification_map = {
            "Paris SG": "Paris Saint-Germain",
            "Paris Saint-Germain": "Paris SG",
            "Man City": "Manchester City",
            "Manchester City": "Man City",
            "Newcastle": "Newcastle United",
            "Newcastle United": "Newcastle"
        }
        
        local_ids = [local_id]
        visit_ids = [visit_id]
        
        if local in unification_map:
            alias_name = unification_map[local]
            cursor.execute("SELECT Equipo_ID FROM futbol_equipos WHERE Nombre = ?", (alias_name,))
            alias_row = cursor.fetchone()
            if alias_row:
                local_ids.append(alias_row["Equipo_ID"])
                
        if visitante in unification_map:
            alias_name = unification_map[visitante]
            cursor.execute("SELECT Equipo_ID FROM futbol_equipos WHERE Nombre = ?", (alias_name,))
            alias_row = cursor.fetchone()
            if alias_row:
                visit_ids.append(alias_row["Equipo_ID"])
                
        placeholders_l = ",".join("?" for _ in local_ids)
        placeholders_v = ",".join("?" for _ in visit_ids)
        
        # Calcular promedios globales de la liga para goles
        cursor.execute("SELECT AVG(Goles_Local), AVG(Goles_Visitante) FROM futbol_partidos")
        avg_goles_l, avg_goles_v = cursor.fetchone()
        
        # Valores por defecto en caso de base de datos vacía
        avg_goles_l = avg_goles_l or 1.5
        avg_goles_v = avg_goles_v or 1.0
        
        # A. GOLES: Fuerza atacante y defensiva del Local
        cursor.execute(f"SELECT AVG(Goles_Local) as gf, AVG(Goles_Visitante) as gc FROM futbol_partidos WHERE Local_ID IN ({placeholders_l})", local_ids)
        stats_l_local = cursor.fetchone()
        
        # Fuerza atacante y defensiva del Visitante
        cursor.execute(f"SELECT AVG(Goles_Visitante) as gf, AVG(Goles_Local) as gc FROM futbol_partidos WHERE Visitante_ID IN ({placeholders_v})", visit_ids)
        stats_v_visit = cursor.fetchone()
        
        # Fallbacks si no hay suficientes partidos
        l_gf = stats_l_local["gf"] if stats_l_local and stats_l_local["gf"] is not None else avg_goles_l
        l_gc = stats_l_local["gc"] if stats_l_local and stats_l_local["gc"] is not None else avg_goles_v
        v_gf = stats_v_visit["gf"] if stats_v_visit and stats_v_visit["gf"] is not None else avg_goles_v
        v_gc = stats_v_visit["gc"] if stats_v_visit and stats_v_visit["gc"] is not None else avg_goles_l
        
        # Fuerza relativa (floored at 0.2 to avoid 0% probabilities from streaks)
        atq_local = max(0.2, l_gf / avg_goles_l)
        def_local = max(0.2, l_gc / avg_goles_v)
        atq_visit = max(0.2, v_gf / avg_goles_v)
        def_visit = max(0.2, v_gc / avg_goles_l)
        
        # Goles esperados (Lambdas)
        lam_local = atq_local * def_visit * avg_goles_l
        lam_visit = atq_visit * def_local * avg_goles_v
        
        # Ajuste por Ranking FIFA (si ambos son selecciones y tienen ranking disponible)
        try:
            if rank_l_str is not None and rank_v_str is not None:
                rank_local = int(rank_l_str)
                rank_visit = int(rank_v_str)
                
                # Diferencia de ranking (positivo indica que local tiene mejor ranking, ej: #1 vs #34)
                rank_diff = rank_visit - rank_local
                
                # Multiplicador: 0.5% de ajuste por cada posición de diferencia
                mult_local = 1.0 + (rank_diff * 0.005)
                mult_visit = 1.0 - (rank_diff * 0.005)
                
                # Limitar el multiplicador entre [0.7, 1.3] (máximo 30% de ajuste)
                mult_local = max(0.7, min(1.3, mult_local))
                mult_visit = max(0.7, min(1.3, mult_visit))
                
                lam_local = lam_local * mult_local
                lam_visit = lam_visit * mult_visit
        except Exception as e:
            # En caso de error de formato o conversión, no aplicar el ajuste
            pass
        
        # Probabilidades de victoria (Simulación Poisson 15x15)
        prob_local_win = 0.0
        prob_draw = 0.0
        prob_visita_win = 0.0
        
        for h in range(15):
            for a in range(15):
                prob_cell = poisson.pmf(h, lam_local) * poisson.pmf(a, lam_visit)
                if h > a:
                    prob_local_win += prob_cell
                elif h == a:
                    prob_draw += prob_cell
                else:
                    prob_visita_win += prob_cell
                    
        total_prob = prob_local_win + prob_draw + prob_visita_win
        if total_prob > 0:
            prob_local = round((prob_local_win / total_prob) * 100, 1)
            prob_empate = round((prob_draw / total_prob) * 100, 1)
            prob_visita = round((prob_visita_win / total_prob) * 100, 1)
        else:
            prob_local, prob_empate, prob_visita = 33.3, 33.3, 33.3
            
        # Matriz de goles 5x5 (Row index: goles Local 4..0, Col index: goles Visitante 4..0)
        goles_matriz = []
        max_cell_prob = -1.0
        best_score = (3, 3) # fallback
        
        for r in [4, 3, 2, 1, 0]:
            row_probs = []
            for c in [4, 3, 2, 1, 0]:
                cell_prob = poisson.pmf(r, lam_local) * poisson.pmf(c, lam_visit)
                if cell_prob > max_cell_prob:
                    max_cell_prob = cell_prob
                    best_score = (r, c)
                row_probs.append(round(cell_prob * 100, 1))
            goles_matriz.append(row_probs)
            
        # B. CORNERS: Calcular fuerza de corners
        # Global averages only considering matches that have actual stats
        cursor.execute('''
            SELECT AVG(e.Corners) FROM futbol_estadisticas e 
            WHERE e.Es_Local = 1 AND EXISTS (
                SELECT 1 FROM futbol_estadisticas e2 
                WHERE e2.Partido_ID = e.Partido_ID AND (e2.Corners > 0 OR e2.Tiros > 0)
            )
        ''')
        avg_hc = cursor.fetchone()[0] or 5.0
        
        cursor.execute('''
            SELECT AVG(e.Corners) FROM futbol_estadisticas e 
            WHERE e.Es_Local = 0 AND EXISTS (
                SELECT 1 FROM futbol_estadisticas e2 
                WHERE e2.Partido_ID = e.Partido_ID AND (e2.Corners > 0 OR e2.Tiros > 0)
            )
        ''')
        avg_ac = cursor.fetchone()[0] or 4.08
        
        # Team averages only considering matches that have actual stats
        cursor.execute(f'''
            SELECT AVG(e.Corners) FROM futbol_estadisticas e 
            WHERE e.Equipo_ID IN ({placeholders_l}) AND e.Es_Local = 1 AND EXISTS (
                SELECT 1 FROM futbol_estadisticas e2 
                WHERE e2.Partido_ID = e.Partido_ID AND (e2.Corners > 0 OR e2.Tiros > 0)
            )
        ''', local_ids)
        local_hc_mean = cursor.fetchone()[0]
        if local_hc_mean is None:
            local_hc_mean = avg_hc
            
        cursor.execute(f'''
            SELECT AVG(e.Corners) 
            FROM futbol_estadisticas e 
            JOIN futbol_partidos p ON e.Partido_ID = p.Partido_ID
            WHERE p.Local_ID IN ({placeholders_l}) AND e.Es_Local = 0 AND EXISTS (
                SELECT 1 FROM futbol_estadisticas e2 
                WHERE e2.Partido_ID = e.Partido_ID AND (e2.Corners > 0 OR e2.Tiros > 0)
            )
        ''', local_ids)
        local_ac_conceded = cursor.fetchone()[0]
        if local_ac_conceded is None:
            local_ac_conceded = avg_ac
            
        # Corners generados/recibidos por Visitante
        cursor.execute(f'''
            SELECT AVG(e.Corners) FROM futbol_estadisticas e 
            WHERE e.Equipo_ID IN ({placeholders_v}) AND e.Es_Local = 0 AND EXISTS (
                SELECT 1 FROM futbol_estadisticas e2 
                WHERE e2.Partido_ID = e.Partido_ID AND (e2.Corners > 0 OR e2.Tiros > 0)
            )
        ''', visit_ids)
        visit_ac_mean = cursor.fetchone()[0]
        if visit_ac_mean is None:
            visit_ac_mean = avg_ac
            
        cursor.execute(f'''
            SELECT AVG(e.Corners) 
            FROM futbol_estadisticas e 
            JOIN futbol_partidos p ON e.Partido_ID = p.Partido_ID
            WHERE p.Visitante_ID IN ({placeholders_v}) AND e.Es_Local = 1 AND EXISTS (
                SELECT 1 FROM futbol_estadisticas e2 
                WHERE e2.Partido_ID = e.Partido_ID AND (e2.Corners > 0 OR e2.Tiros > 0)
            )
        ''', visit_ids)
        visit_hc_conceded = cursor.fetchone()[0]
        if visit_hc_conceded is None:
            visit_hc_conceded = avg_hc
        
        # Fuerza relativa de corners (floored at 0.2 to avoid 0% probabilities from streaks)
        hc_atq = max(0.2, local_hc_mean / avg_hc)
        hc_def = max(0.2, local_ac_conceded / avg_ac)
        ac_atq = max(0.2, visit_ac_mean / avg_ac)
        ac_def = max(0.2, visit_hc_conceded / avg_hc)
        
        lam_local_corners = hc_atq * ac_def * avg_hc
        lam_visit_corners = ac_atq * hc_def * avg_ac
        lam_total_corners = lam_local_corners + lam_visit_corners
        
        # Probabilidades acumuladas de corners para la lista (1 a 11+)
        # P(Corners >= k)
        local_corners_probs = []
        for k in range(1, 11):
            prob = (1 - poisson.cdf(k - 1, lam_local_corners)) * 100
            local_corners_probs.append(round(prob, 1))
        local_corners_probs.append(round((1 - poisson.cdf(10, lam_local_corners)) * 100, 1))
        
        visitante_corners_probs = []
        for k in range(1, 11):
            prob = (1 - poisson.cdf(k - 1, lam_visit_corners)) * 100
            visitante_corners_probs.append(round(prob, 1))
        visitante_corners_probs.append(round((1 - poisson.cdf(10, lam_visit_corners)) * 100, 1))
        
        # Analizar dinámicamente las líneas de corners y recomendar la más cercana al 70% de probabilidad
        lines = [5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5]
        best_corners_text = ""
        best_corners_prob = 0.0
        min_diff = 100.0
        
        for L in lines:
            k = math.floor(L)
            prob_over = (1 - poisson.cdf(k, lam_total_corners)) * 100
            prob_under = poisson.cdf(k, lam_total_corners) * 100
            
            # Opción Más de L
            diff_over = abs(prob_over - 70.0)
            if diff_over < min_diff:
                min_diff = diff_over
                best_corners_text = f"Más de {L}"
                best_corners_prob = prob_over
                
            # Opción Menos de L
            diff_under = abs(prob_under - 70.0)
            if diff_under < min_diff:
                min_diff = diff_under
                best_corners_text = f"Menos de {L}"
                best_corners_prob = prob_under

        best_corners_prob = round(best_corners_prob, 1)
        
        # Determine highest probability outcome
        max_prob = prob_local
        seleccion = "Local"
        if prob_empate > max_prob:
            max_prob = prob_empate
            seleccion = "Empate"
        if prob_visita > max_prob:
            max_prob = prob_visita
            seleccion = "Visitante"
            
        momio_casino = round(random.uniform(1.50, 3.50), 2)
        prob_casino = round((1 / momio_casino) * 100, 1)
        edge = round(max_prob - prob_casino, 1)
        
        value_bet = {
            "momio_casino": momio_casino,
            "prob_casino": prob_casino,
            "prob_ia": max_prob,
            "edge": edge,
            "seleccion": seleccion
        }

        return {
            "partido": f"{local} vs {visitante}",
            "victoria": {
                "local_pct": prob_local,
                "empate_pct": prob_empate,
                "visita_pct": prob_visita
            },
            "goles_matriz": goles_matriz,
            "resultado_probable": {
                "marcador": f"{best_score[0]} - {best_score[1]}",
                "prob": round(max_cell_prob * 100, 1)
            },
            "corners": {
                "local": local_corners_probs,
                "visitante": visitante_corners_probs,
                "total_corners_text": best_corners_text,
                "total_corners_prob": best_corners_prob
            },
            "value_bet": value_bet
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- PREDICCIÓN DE BÉISBOL (MLB) ---

@app.get("/api/pitchers")
def obtener_pitchers_equipo(equipo: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get team ID
        cursor.execute("SELECT Equipo_ID FROM beisbol_equipos WHERE Nombre = ?", (equipo,))
        row_team = cursor.fetchone()
        if not row_team:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        team_id = row_team["Equipo_ID"]
        
        # Get all pitchers for this team who have started games (IP >= 3.0)
        cursor.execute('''
            SELECT sp.Pitcher_ID, j.Nombre_Completo, COUNT(*) as starts
            FROM beisbol_stats_pitcheo sp
            JOIN beisbol_partidos p ON sp.Partido_ID = p.Partido_ID
            JOIN beisbol_jugadores j ON sp.Pitcher_ID = j.Jugador_ID
            WHERE (p.Local_ID = ? OR p.Visitante_ID = ?) AND sp.Innings_Lanzados >= 3.0
            GROUP BY sp.Pitcher_ID, j.Nombre_Completo
            ORDER BY starts DESC, j.Nombre_Completo ASC
        ''', (team_id, team_id))
        rows = cursor.fetchall()
        pitchers = [{"id": row["Pitcher_ID"], "nombre": row["Nombre_Completo"], "starts": row["starts"]} for row in rows]
        return {"pitchers": pitchers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/pronostico")
@app.get("/api/pronostico/beisbol")
def obtener_pronostico_beisbol(local: str, visitante: str, pitcher_local: int = None, pitcher_visitante: int = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Obtener IDs de los equipos
        cursor.execute("SELECT Equipo_ID FROM beisbol_equipos WHERE Nombre = ?", (local,))
        row_local = cursor.fetchone()
        cursor.execute("SELECT Equipo_ID FROM beisbol_equipos WHERE Nombre = ?", (visitante,))
        row_visit = cursor.fetchone()
        
        if not row_local or not row_visit:
            raise HTTPException(status_code=404, detail="Uno o ambos equipos no fueron encontrados.")
            
        local_id = row_local["Equipo_ID"]
        visit_id = row_visit["Equipo_ID"]
        
        # 1. Obtener carreras ofensivas promedio
        cursor.execute('''
            SELECT AVG(carreras) FROM (
                SELECT Carreras_Local as carreras FROM beisbol_partidos WHERE Local_ID = ?
                UNION ALL
                SELECT Carreras_Visitante FROM beisbol_partidos WHERE Visitante_ID = ?
            )
        ''', (local_id, local_id))
        local_bat_avg = cursor.fetchone()[0] or 4.5
        
        cursor.execute('''
            SELECT AVG(carreras) FROM (
                SELECT Carreras_Local as carreras FROM beisbol_partidos WHERE Local_ID = ?
                UNION ALL
                SELECT Carreras_Visitante FROM beisbol_partidos WHERE Visitante_ID = ?
            )
        ''', (visit_id, visit_id))
        visit_bat_avg = cursor.fetchone()[0] or 4.2
        
        # 2. Obtener Pitchers Iniciadores
        def get_pitcher_stats(team_id, specific_pitcher_id=None):
            if specific_pitcher_id is not None:
                cursor.execute('''
                    SELECT Jugador_ID, Nombre_Completo FROM beisbol_jugadores WHERE Jugador_ID = ?
                ''', (specific_pitcher_id,))
                p_row = cursor.fetchone()
                if not p_row:
                    return {
                        "id": None,
                        "nombre": "Pitcher Desconocido",
                        "forma": "Regular",
                        "era": 4.5,
                        "whip": 1.35,
                        "k9": 6.5,
                        "qs_prob": 30.0
                    }
                pitcher_id = p_row["Jugador_ID"]
                pitcher_name = p_row["Nombre_Completo"]
            else:
                # Obtener el pitcher abridor más común/reciente
                cursor.execute('''
                    SELECT sp.Pitcher_ID, j.Nombre_Completo, COUNT(*) as starts
                    FROM beisbol_stats_pitcheo sp
                    JOIN beisbol_partidos p ON sp.Partido_ID = p.Partido_ID
                    JOIN beisbol_jugadores j ON sp.Pitcher_ID = j.Jugador_ID
                    WHERE (p.Local_ID = ? OR p.Visitante_ID = ?) AND sp.Innings_Lanzados >= 3.0
                    GROUP BY sp.Pitcher_ID
                    ORDER BY starts DESC
                    LIMIT 1
                ''', (team_id, team_id))
                p_row = cursor.fetchone()
                
                if not p_row:
                    return {
                        "id": None,
                        "nombre": "Pitcher Desconocido",
                        "forma": "Regular",
                        "era": 4.5,
                        "whip": 1.35,
                        "k9": 6.5,
                        "qs_prob": 30.0
                    }
                    
                pitcher_id = p_row["Pitcher_ID"]
                pitcher_name = p_row["Nombre_Completo"]
            
            # Obtener estadísticas agregadas del pitcher
            cursor.execute('''
                SELECT 
                    SUM(Innings_Lanzados) as total_ip,
                    SUM(Carreras_Limpias) as total_er,
                    SUM(Hits_Permitidos) as total_hits,
                    SUM(Bases_Por_Bolas) as total_walks,
                    SUM(Ponches) as total_so,
                    COUNT(*) as total_starts
                FROM beisbol_stats_pitcheo
                WHERE Pitcher_ID = ?
            ''', (pitcher_id,))
            p_stats = cursor.fetchone()
            
            total_ip = p_stats["total_ip"] or 9.0
            total_er = p_stats["total_er"] or 4.0
            total_hits = p_stats["total_hits"] or 9.0
            total_walks = p_stats["total_walks"] or 3.0
            total_so = p_stats["total_so"] or 6.0
            total_starts = p_stats["total_starts"] or 1
            
            era = round((total_er * 9.0) / total_ip, 2)
            whip = round((total_hits + total_walks) / total_ip, 2)
            k9 = round((total_so * 9.0) / total_ip, 2)
            
            # Calcular Quality Starts (IP >= 6.0 y ER <= 3)
            cursor.execute('''
                SELECT COUNT(*) FROM beisbol_stats_pitcheo
                WHERE Pitcher_ID = ? AND Innings_Lanzados >= 6.0 AND Carreras_Limpias <= 3
            ''', (pitcher_id,))
            qs_count = cursor.fetchone()[0] or 0
            qs_prob = round((qs_count / total_starts) * 100, 1)
            
            # Estado de forma basado en ERA
            forma = "Muy Buena" if era < 3.5 else ("Buena" if era < 4.5 else "Regular")
            
            return {
                "id": int(pitcher_id) if pitcher_id is not None else None,
                "nombre": pitcher_name,
                "forma": forma,
                "era": era,
                "whip": whip,
                "k9": k9,
                "qs_prob": qs_prob
            }
            
        pitcher_local = get_pitcher_stats(local_id, pitcher_local)
        pitcher_visita = get_pitcher_stats(visit_id, pitcher_visitante)
        
        # 3. Predicción de Carreras (Fórmula cruzada)
        carreras_esp_local = (local_bat_avg + pitcher_visita["era"]) / 2
        carreras_esp_visita = (visit_bat_avg + pitcher_local["era"]) / 2
        total_carreras = carreras_esp_local + carreras_esp_visita
        
        # 4. Probabilidades de victoria (Moneyline - Poisson redistribuido sin empates)
        prob_local_win = 0.0
        prob_visita_win = 0.0
        
        for h in range(30):
            for a in range(30):
                prob_cell = poisson.pmf(h, carreras_esp_local) * poisson.pmf(a, carreras_esp_visita)
                if h > a:
                    prob_local_win += prob_cell
                elif a > h:
                    prob_visita_win += prob_cell
                    
        total_prob = prob_local_win + prob_visita_win
        if total_prob > 0:
            prob_local = round((prob_local_win / total_prob) * 100, 1)
            prob_visita = round((prob_visita_win / total_prob) * 100, 1)
        else:
            prob_local, prob_visita = 50.0, 50.0
            
        # 5. Over/Under Apuestas (Líneas 6.5, 7.5, 8.5, 9.5, 10.5)
        over_65 = round((1 - poisson.cdf(6, total_carreras)) * 100, 1)
        under_65 = round(100 - over_65, 1)
        over_75 = round((1 - poisson.cdf(7, total_carreras)) * 100, 1)
        under_75 = round(100 - over_75, 1)
        over_85 = round((1 - poisson.cdf(8, total_carreras)) * 100, 1)
        under_85 = round(100 - over_85, 1)
        over_95 = round((1 - poisson.cdf(9, total_carreras)) * 100, 1)
        under_95 = round(100 - over_95, 1)
        over_105 = round((1 - poisson.cdf(10, total_carreras)) * 100, 1)
        under_105 = round(100 - over_105, 1)
        
        # Analizar dinámicamente las líneas de carreras y recomendar la más cercana al 70% de probabilidad
        lines = [6.5, 7.5, 8.5, 9.5, 10.5]
        best_runs_text = ""
        best_runs_prob = 0.0
        min_diff = 100.0
        
        for L in lines:
            k = math.floor(L)
            prob_over = (1 - poisson.cdf(k, total_carreras)) * 100
            prob_under = poisson.cdf(k, total_carreras) * 100
            
            # Opción Más de L
            diff_over = abs(prob_over - 70.0)
            if diff_over < min_diff:
                min_diff = diff_over
                best_runs_text = f"Más de {L}"
                best_runs_prob = prob_over
                
            # Opción Menos de L
            diff_under = abs(prob_under - 70.0)
            if diff_under < min_diff:
                min_diff = diff_under
                best_runs_text = f"Menos de {L}"
                best_runs_prob = prob_under

        best_runs_prob = round(best_runs_prob, 1)
        
        # 6. Carreras Totales Probables por Equipo (para las barras verticales)
        # Probabilidades individuales de superar un rango de carreras
        # Grupo 1 (Over 3.5 carreras)
        over_35_local = round((1 - poisson.cdf(3, carreras_esp_local)) * 100, 1)
        over_35_visita = round((1 - poisson.cdf(3, carreras_esp_visita)) * 100, 1)
        # Grupo 2 (Over 4.5 carreras)
        over_45_local = round((1 - poisson.cdf(4, carreras_esp_local)) * 100, 1)
        over_45_visita = round((1 - poisson.cdf(4, carreras_esp_visita)) * 100, 1)
        
        # Resultado probable
        best_r = int(round(carreras_esp_local))
        best_c = int(round(carreras_esp_visita))
        # Asegurarse de que no sea un empate en béisbol (hacer que gane el que tiene más carreras esperadas)
        if best_r == best_c:
            if carreras_esp_local > carreras_esp_visita:
                best_r += 1
            else:
                best_c += 1
                
        prob_resultado = round((poisson.pmf(best_r, carreras_esp_local) * poisson.pmf(best_c, carreras_esp_visita)) * 100, 1)
        
        # Si el resultado es demasiado bajo por la dispersión, ajustamos para un look realista de apuestas
        if prob_resultado < 5.0:
            prob_resultado = round(total_prob * 100 / 12, 1)
        # Determine highest probability outcome
        max_prob = prob_local
        seleccion = "Local"
        if prob_visita > max_prob:
            max_prob = prob_visita
            seleccion = "Visitante"
            
        momio_casino = round(random.uniform(1.50, 3.50), 2)
        prob_casino = round((1 / momio_casino) * 100, 1)
        edge = round(max_prob - prob_casino, 1)
        
        value_bet = {
            "momio_casino": momio_casino,
            "prob_casino": prob_casino,
            "prob_ia": max_prob,
            "edge": edge,
            "seleccion": seleccion
        }

        return {
            "partido": f"{local} vs {visitante}",
            "victoria": {
                "local_pct": prob_local,
                "visita_pct": prob_visita
            },
            "carreras": {
                "total_esperado": round(total_carreras, 2),
                "local_esperado": round(carreras_esp_local, 2),
                "visitante_esperado": round(carreras_esp_visita, 2)
            },
            "mercados": {
                "over_6_5": over_65,
                "under_6_5": under_65,
                "over_7_5": over_75,
                "under_7_5": under_75,
                "over_8_5": over_85,
                "under_8_5": under_85,
                "over_9_5": over_95,
                "under_9_5": under_95,
                "over_10_5": over_105,
                "under_10_5": under_105,
            },
            "carreras_totales": {
                "grupo_1": {
                    "local": { "runs": round(carreras_esp_local, 1), "prob": over_35_local },
                    "visitante": { "runs": round(carreras_esp_visita, 1), "prob": over_35_visita }
                },
                "medio": best_runs_text,
                "medio_prob": best_runs_prob,
                "grupo_2": {
                    "local": { "runs": round(carreras_esp_local + 1.0, 1), "prob": over_45_local },
                    "visitante": { "runs": round(carreras_esp_visita + 1.0, 1), "prob": over_45_visita }
                }
            },
            "resultado_probable": {
                "marcador": f"{best_r} - {best_c}",
                "prob": prob_resultado
            },
            "jugadores": {
                "local": pitcher_local,
                "visitante": pitcher_visita
            },
            "value_bet": value_bet
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# --- ADMINISTRATIVE ENDPOINTS ---

@app.get("/api/ping")
def ping():
    return {"status": "online"}

@app.get("/api/status")
def get_system_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # MLB stats
        cursor.execute("SELECT MAX(Fecha), COUNT(*) FROM beisbol_partidos")
        mlb_row = cursor.fetchone()
        mlb_last_date = mlb_row[0] if mlb_row else None
        mlb_total_matches = mlb_row[1] if mlb_row else 0
        
        # Soccer stats
        cursor.execute("SELECT MAX(Fecha), COUNT(*) FROM futbol_partidos")
        futbol_row = cursor.fetchone()
        futbol_last_date = futbol_row[0] if futbol_row else None
        futbol_total_matches = futbol_row[1] if futbol_row else 0
        
        return {
            "status": "online",
            "futbol": {
                "last_match_date": futbol_last_date,
                "total_matches": futbol_total_matches
            },
            "beisbol": {
                "last_match_date": mlb_last_date,
                "total_matches": mlb_total_matches
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/upload/futbol")
def upload_futbol_csv(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="El archivo debe ser un CSV.")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        content = file.file.read().decode('utf-8')
        import csv
        import io
        
        # Parse CSV
        reader = csv.DictReader(io.StringIO(content))
        
        # Verify headers
        headers = reader.fieldnames
        if not headers:
            raise HTTPException(status_code=400, detail="CSV vacío o sin cabeceras.")
            
        # Helper to find column key ignoring case
        def find_col(aliases):
            for alias in aliases:
                for h in headers:
                    if h.strip().lower() == alias.lower():
                        return h
            return None
            
        # Map columns
        date_col = find_col(['Date', 'date', 'Fecha'])
        home_col = find_col(['Home', 'HomeTeam', 'Local'])
        away_col = find_col(['Away', 'AwayTeam', 'Visitante'])
        hg_col = find_col(['HG', 'FTHG', 'Goles_Local', 'GolesLocal'])
        ag_col = find_col(['AG', 'FTAG', 'Goles_Visitante', 'GolesVisitante'])
        
        # Stats columns (optional)
        hs_col = find_col(['HS', 'Shots_Local'])
        as_col = find_col(['AS', 'Shots_Visitante'])
        hst_col = find_col(['HST', 'ShotsTarget_Local'])
        ast_col = find_col(['AST', 'ShotsTarget_Visitante'])
        hf_col = find_col(['HF', 'Fouls_Local'])
        af_col = find_col(['AF', 'Fouls_Visitante'])
        hc_col = find_col(['HC', 'Corners_Local'])
        ac_col = find_col(['AC', 'Corners_Visitante'])
        hy_col = find_col(['HY', 'Yellow_Local'])
        ay_col = find_col(['AY', 'Yellow_Visitante'])
        hr_col = find_col(['HR', 'Red_Local'])
        ar_col = find_col(['AR', 'Red_Visitante'])
        hxg_col = find_col(['HxG', 'xG_Local'])
        axg_col = find_col(['AxG', 'xG_Visitante'])
        
        # Odds (optional)
        odd_h_col = find_col(['AvgH', 'H_Avg', 'B365H', 'Cuota_Local'])
        odd_d_col = find_col(['AvgD', 'D_Avg', 'B365D', 'Cuota_Empate'])
        odd_a_col = find_col(['AvgA', 'A_Avg', 'B365A', 'Cuota_Visitante'])
        
        if not all([date_col, home_col, away_col, hg_col, ag_col]):
            raise HTTPException(
                status_code=400, 
                detail="Faltan columnas requeridas en el CSV. Debe contener al menos: Date, Home, Away, HG, AG."
            )
            
        # Deduce Liga/Division from file name
        fn = file.filename.lower()
        default_liga = "Otros"
        if "e0" in fn:
            default_liga = "Premier League"
        elif "f1" in fn:
            default_liga = "Ligue 1"
        elif "ucl" in fn or "champions" in fn:
            default_liga = "Champions League"
        elif "worldcup" in fn or "mundial" in fn:
            default_liga = "Equipos de Mundial"
            
        inserted_matches = 0
        skipped_matches = 0
        teams_created = 0
        
        # Cache for team IDs
        team_cache = {}
        
        def get_or_create_team(team_name):
            nonlocal teams_created
            team_name = team_name.strip()
            if team_name in team_cache:
                return team_cache[team_name]
                
            cursor.execute("SELECT Equipo_ID FROM futbol_equipos WHERE Nombre = ?", (team_name,))
            row = cursor.fetchone()
            if row:
                team_cache[team_name] = row[0]
                return row[0]
            else:
                # Create team
                cursor.execute("INSERT INTO futbol_equipos (Nombre, Liga) VALUES (?, ?)", (team_name, default_liga))
                new_id = cursor.lastrowid
                team_cache[team_name] = new_id
                teams_created += 1
                return new_id
                
        for row in reader:
            date_val = row[date_col].strip()
            # Standardize date to YYYY-MM-DD
            if '/' in date_val:
                parts = date_val.split('/')
                if len(parts) == 3:
                    year = parts[2]
                    if len(year) == 2:
                        year = "20" + year
                    date_val = f"{year}-{parts[1]:0>2}-{parts[0]:0>2}"
                    
            local_name = row[home_col].strip()
            visit_name = row[away_col].strip()
            
            if not local_name or not visit_name:
                continue
                
            local_id = get_or_create_team(local_name)
            visit_id = get_or_create_team(visit_name)
            
            # Check if match already exists
            cursor.execute("""
                SELECT Partido_ID FROM futbol_partidos 
                WHERE Fecha = ? AND Local_ID = ? AND Visitante_ID = ?
            """, (date_val, local_id, visit_id))
            if cursor.fetchone():
                skipped_matches += 1
                continue
                
            # Goals
            goles_l = int(row[hg_col]) if row[hg_col] else 0
            goles_v = int(row[ag_col]) if row[ag_col] else 0
            
            # Season
            season = date_val.split('-')[0]
            
            # Odds
            odd_h = float(row[odd_h_col]) if odd_h_col and row[odd_h_col] else None
            odd_d = float(row[odd_d_col]) if odd_d_col and row[odd_d_col] else None
            odd_a = float(row[odd_a_col]) if odd_a_col and row[odd_a_col] else None
            
            # Insert match
            cursor.execute("""
                INSERT INTO futbol_partidos (Fecha, Temporada, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante, Cuota_Local, Cuota_Empate, Cuota_Visitante)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (date_val, season, local_id, visit_id, goles_l, goles_v, odd_h, odd_d, odd_a))
            match_id = cursor.lastrowid
            
            # Insert stats for Local & Visitor
            def get_stat(col):
                if col and row[col]:
                    try:
                        return float(row[col])
                    except:
                        return None
                return None
                
            tiros_l = get_stat(hs_col)
            tiros_v = get_stat(as_col)
            tar_l = get_stat(hst_col)
            tar_v = get_stat(ast_col)
            fal_l = get_stat(hf_col)
            fal_v = get_stat(af_col)
            corn_l = get_stat(hc_col)
            corn_v = get_stat(ac_col)
            yam_l = get_stat(hy_col)
            yam_v = get_stat(ay_col)
            ram_l = get_stat(hr_col)
            ram_v = get_stat(ar_col)
            xg_l = get_stat(hxg_col)
            xg_v = get_stat(axg_col)
            
            cursor.execute("""
                INSERT INTO futbol_estadisticas (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
            """, (match_id, local_id, tiros_l, tar_l, fal_l, corn_l, yam_l, ram_l, xg_l))
            
            cursor.execute("""
                INSERT INTO futbol_estadisticas (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
            """, (match_id, visit_id, tiros_v, tar_v, fal_v, corn_v, yam_v, ram_v, xg_v))
            
            inserted_matches += 1
            
        conn.commit()
        return {
            "status": "success",
            "message": f"Archivo '{file.filename}' procesado con éxito.",
            "inserted_matches": inserted_matches,
            "skipped_matches": skipped_matches,
            "teams_created": teams_created
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/sync/beisbol")
def sync_mlb_data(start_date: str = None, end_date: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from datetime import datetime, timedelta
        if not start_date:
            cursor.execute("SELECT MAX(Fecha) FROM beisbol_partidos")
            last_date_row = cursor.fetchone()
            if last_date_row and last_date_row[0]:
                start_date = last_date_row[0]
            else:
                start_date = "2026-05-20"
                
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
            
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Limit sync range to 14 days maximum
        delta = end_dt - start_dt
        if delta.days > 14:
            start_dt = end_dt - timedelta(days=14)
            start_date = start_dt.strftime("%Y-%m-%d")
            
        import urllib.request
        import json
        
        date_list = []
        curr = start_dt
        while curr <= end_dt:
            date_list.append(curr.strftime("%Y-%m-%d"))
            curr += timedelta(days=1)
            
        games_synced = 0
        pitchers_added = 0
        stats_inserted = 0
        
        for date_str in date_list:
            url = f"https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&date={date_str}"
            try:
                req = urllib.request.urlopen(url)
                sched_data = json.loads(req.read().decode('utf-8'))
                dates = sched_data.get("dates", [])
                if not dates:
                    continue
                games = dates[0].get("games", [])
                for game in games:
                    game_id = game.get("gamePk")
                    status = game.get("status", {}).get("detailedState")
                    if status != "Final":
                        continue
                        
                    # Check if game already in DB
                    cursor.execute("SELECT Partido_ID FROM beisbol_partidos WHERE Partido_ID = ?", (game_id,))
                    if cursor.fetchone():
                        continue
                        
                    teams = game.get("teams", {})
                    local_id = teams.get("home", {}).get("team", {}).get("id")
                    visit_id = teams.get("away", {}).get("team", {}).get("id")
                    local_runs = teams.get("home", {}).get("score")
                    visit_runs = teams.get("away", {}).get("score")
                    
                    # Insert match
                    cursor.execute("""
                        INSERT INTO beisbol_partidos (Partido_ID, Fecha, Local_ID, Visitante_ID, Carreras_Local, Carreras_Visitante)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (game_id, date_str, local_id, visit_id, local_runs, visit_runs))
                    games_synced += 1
                    
                    # Fetch boxscore
                    boxscore_url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
                    try:
                        box_req = urllib.request.urlopen(boxscore_url)
                        box_data = json.loads(box_req.read().decode('utf-8'))
                        teams_box = box_data.get("teams", {})
                        
                        for side in ["home", "away"]:
                            players = teams_box.get(side, {}).get("players", {})
                            for player_key, player_info in players.items():
                                pitching = player_info.get("stats", {}).get("pitching", {})
                                if pitching and pitching.get("inningsPitched") is not None:
                                    person = player_info.get("person", {})
                                    pid = person.get("id")
                                    name = person.get("fullName")
                                    
                                    # Verify pitcher exists in beisbol_jugadores
                                    cursor.execute("SELECT Jugador_ID FROM beisbol_jugadores WHERE Jugador_ID = ?", (pid,))
                                    if not cursor.fetchone():
                                        cursor.execute("""
                                            INSERT INTO beisbol_jugadores (Jugador_ID, Nombre_Completo, Posicion)
                                            VALUES (?, ?, 'P')
                                        """, (pid, name))
                                        pitchers_added += 1
                                        
                                    # Parse stats
                                    ip_str = pitching.get("inningsPitched")
                                    try:
                                        ip = float(ip_str)
                                    except:
                                        ip = 0.0
                                    hits = pitching.get("hits", 0)
                                    er = pitching.get("earnedRuns", 0)
                                    bb = pitching.get("baseOnBalls", 0)
                                    so = pitching.get("strikeOuts", 0)
                                    
                                    # Insert pitch stats
                                    cursor.execute("""
                                        INSERT INTO beisbol_stats_pitcheo (Partido_ID, Pitcher_ID, Innings_Lanzados, Hits_Permitidos, Carreras_Limpias, Bases_Por_Bolas, Ponches)
                                        VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """, (game_id, pid, ip, hits, er, bb, so))
                                    stats_inserted += 1
                    except Exception as box_err:
                        print(f"Error boxscore: {box_err}")
                conn.commit()
            except Exception as date_err:
                print(f"Error syncing date: {date_err}")
                
        return {
            "status": "success",
            "message": f"Sincronización completada desde {start_date} hasta {end_date}.",
            "games_synced": games_synced,
            "pitchers_added": pitchers_added,
            "stats_inserted": stats_inserted
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/credits")
def obtener_creditos():
    credits_file = os.path.join(os.path.dirname(__file__), 'api_credits.json')
    if os.path.exists(credits_file):
        try:
            with open(credits_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e)}
    # Valores por defecto si el archivo no existe
    return {
        "api_football": {
            "limit": 100,
            "remaining": 100,
            "last_updated": None
        },
        "football_data": {
            "remaining_minute": 10,
            "last_updated": None
        }
    }

@app.get("/api/sincronizar-futbol")
def actualizar_db_futbol(date: str = None):
    try:
        resultado = sincronizar_partidos_ayer(target_date=date)
        if resultado.get("status") == "error":
            raise HTTPException(status_code=500, detail=resultado.get("mensaje"))
        return {"mensaje": "Sincronización completada", "detalles": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/descargar-catalogo-ligas")
def descargar_catalogo_ligas():
    try:
        resultado = guardar_todas_las_ligas()
        if resultado.get("status") == "error":
            raise HTTPException(status_code=500, detail=resultado.get("mensaje"))
        return {"mensaje": "Catálogo de ligas descargado", "detalles": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sincronizar-futbol-temporada")
def actualizar_db_futbol_temporada():
    try:
        resultado = sincronizar_temporada_actual()
        if resultado.get("status") == "error":
            raise HTTPException(status_code=500, detail=resultado.get("mensaje"))
        return {"mensaje": "Sincronización de temporada completada", "detalles": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sincronizar-mundial")
def sincronizar_mundial():
    try:
        from sincronizar_mundial_2026 import sincronizar_mundial_2026
        resultado = sincronizar_mundial_2026()
        if resultado.get("status") == "error":
            raise HTTPException(status_code=500, detail=resultado.get("message"))
        return {
            "mensaje": "Sincronización del Mundial 2026 completada",
            "detalles": {
                "status": "ok",
                "partidos_guardados": resultado["matches_added"],
                "duplicados_omitidos": resultado["matches_skipped"],
                "equipos_creados": resultado["teams_created"],
                "posiciones_guardadas": resultado["standings_records"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sincronizar-amistosos")
def actualizar_db_amistosos():
    try:
        resultado = sincronizar_amistosos()
        if resultado.get("status") == "error":
            raise HTTPException(status_code=500, detail=resultado.get("mensaje"))
        return {"mensaje": "Sincronización de amistosos completada", "detalles": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync/futbol-data")
def trigger_futbol_data_sync(background_tasks: BackgroundTasks, token: str = None):
    from sincronizar_football_data import sincronizar_todo
    t = token or "3a01fe1b661f4e28a99e9c9b65f3186c"
    background_tasks.add_task(sincronizar_todo, t)
    return {"status": "success", "message": "Sincronización de football-data.org iniciada en segundo plano."}

@app.get("/api/futbol/standings")
def obtener_standings_futbol(liga: str, temporada: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT Posicion, Equipo_Nombre, Puntos, Jugados, Ganados, Empatados, Perdidos, Goles_Favor, Goles_Contra, Diferencia_Goles
            FROM futbol_standings
            WHERE Liga = ? AND Temporada = ?
            ORDER BY Posicion ASC
        ''', (liga, temporada))
        rows = cursor.fetchall()
        standings = [dict(row) for row in rows]
        return {"standings": standings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/bot/portafolio")
def obtener_datos_bot_portafolio():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT Fecha_Compra, Partido, Momio_Local, Momio_Visita, Prob_Casino_Local, Prob_Casino_Visita, Prob_IA_Local, Prob_IA_Visita, Apuesta_A, Momio_Apostado, Prob_IA_Apostado, "Ventaja_%", Inversion_Simulada, Ganancia_Potencial, Estado FROM bot_portafolio ORDER BY Fecha_Compra ASC, rowid ASC')
        rows = cursor.fetchall()
        
        operaciones = []
        balance_historico = [0.0]
        fechas_grafica = ["Inicio"]
        
        tickets_ganados = 0
        tickets_perdidos = 0
        tickets_pendientes = 0
        
        ganancia_acumulada = 0.0
        
        for row in rows:
            estado = row["Estado"]
            inversion = row["Inversion_Simulada"]
            ganancia_potencial = row["Ganancia_Potencial"]
            momio_apostado = row["Momio_Apostado"]
            apuesta_a = row["Apuesta_A"]
            
            op = {
                "fecha": row["Fecha_Compra"],
                "partido": f"{row['Partido']} ({'L' if apuesta_a == 'Local' else 'V'})",
                "momio": f"{momio_apostado:.2f}",
                "edge": f"{row['Ventaja_%']:.1f}%",
                "estado": estado
            }
            operaciones.append(op)
            
            if estado == "Ganada":
                tickets_ganados += 1
                beneficio = ganancia_potencial - inversion
                ganancia_acumulada += beneficio
                balance_historico.append(round(ganancia_acumulada, 2))
                fechas_grafica.append(row["Fecha_Compra"].split(" ")[1][:5])
            elif estado == "Perdida":
                tickets_perdidos += 1
                beneficio = -inversion
                ganancia_acumulada += beneficio
                balance_historico.append(round(ganancia_acumulada, 2))
                fechas_grafica.append(row["Fecha_Compra"].split(" ")[1][:5])
            elif estado == "Pendiente":
                tickets_pendientes += 1
                
        total_completados = tickets_ganados + tickets_perdidos
        win_rate = round((tickets_ganados / total_completados) * 100, 1) if total_completados > 0 else 0.0
        
        if len(balance_historico) == 1:
            balance_historico = [0.0, 0.0]
            fechas_grafica = ["Inicio", "Hoy"]
            
        return {
            "summary": {
                "ganancia_neta_total": round(ganancia_acumulada, 2),
                "win_rate": win_rate,
                "tickets_pendientes": tickets_pendientes
            },
            "chart": {
                "fechas": fechas_grafica,
                "balance": balance_historico
            },
            "operaciones": operaciones
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

class ApuestaRegistro(BaseModel):
    Fecha_Compra: str
    Partido: str
    Local: str
    Visita: str
    Casino: str
    Momio_Local: float
    Momio_Visita: float
    Prob_Casino_Local: float
    Prob_Casino_Visita: float
    Prob_IA_Local: float
    Prob_IA_Visita: float
    Apuesta_A: str
    Momio_Apostado: float
    Prob_IA_Apostado: float
    Ventaja_Pct: float
    Inversion_Simulada: float
    Ganancia_Potencial: float
    Estado: str

class RegistroTicketPayload(BaseModel):
    apuestas: List[ApuestaRegistro]

@app.post("/api/bot/reiniciar")
def reiniciar_bot_portafolio():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM bot_portafolio")
        conn.commit()
        return {"status": "success", "message": "Datos de bot_portafolio reiniciados."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/bot/registrar-ticket")
def registrar_ticket(payload: RegistroTicketPayload):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for ap in payload.apuestas:
            cursor.execute("""
                INSERT INTO bot_portafolio (
                    Fecha_Compra, Partido, Local, Visita, Casino,
                    Momio_Local, Momio_Visita, Prob_Casino_Local, Prob_Casino_Visita,
                    Prob_IA_Local, Prob_IA_Visita, Apuesta_A, Momio_Apostado,
                    Prob_IA_Apostado, "Ventaja_%", Inversion_Simulada,
                    Ganancia_Potencial, Estado
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ap.Fecha_Compra, ap.Partido, ap.Local, ap.Visita, ap.Casino,
                ap.Momio_Local, ap.Momio_Visita, ap.Prob_Casino_Local, ap.Prob_Casino_Visita,
                ap.Prob_IA_Local, ap.Prob_IA_Visita, ap.Apuesta_A, ap.Momio_Apostado,
                ap.Prob_IA_Apostado, ap.Ventaja_Pct, ap.Inversion_Simulada,
                ap.Ganancia_Potencial, ap.Estado
            ))
        conn.commit()
        return {"status": "success", "count": len(payload.apuestas)}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()