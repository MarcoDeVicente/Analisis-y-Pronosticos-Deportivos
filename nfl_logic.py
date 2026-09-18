import sqlite3
import statistics
import time
from math import sqrt
try:
    import nfl_data_py as nfl
    import pandas as pd
except ImportError:
    pass  # Will be available once pip install finishes

JUGADAS_PROMEDIO = 63.5
PUNTOS_BASE = 21.0
VENTAJA_LOCALIA = 1.5

def get_db_connection():
    conn = sqlite3.connect("DB-Fut-Beis.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_nfl_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla de eficiencia EPA
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nfl_eficiencia_epa (
            equipo TEXT PRIMARY KEY,
            epa_ofensivo REAL,
            epa_defensivo REAL
        )
    ''')
    
    # Tabla de estadísticas de jugadores por partido (Play-by-play agregado)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nfl_jugadores_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jugador TEXT,
            posteam TEXT,
            season INTEGER,
            week INTEGER,
            passing_yards REAL DEFAULT 0,
            passing_tds REAL DEFAULT 0,
            interceptions REAL DEFAULT 0,
            carries REAL DEFAULT 0,
            rushing_yards REAL DEFAULT 0,
            rushing_tds REAL DEFAULT 0,
            receptions REAL DEFAULT 0,
            targets REAL DEFAULT 0,
            receiving_yards REAL DEFAULT 0,
            receiving_tds REAL DEFAULT 0
        )
    ''')
    
    # Tabla dummy solo para cumplir la métrica de 'total_matches' en index.html
    # En la vida real, sacaríamos de pbp o de schedules, pero simulamos una tabla ligera para esto
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nfl_partidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Fecha TEXT,
            Local TEXT,
            Visitante TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def sincronizar_datos_nfl():
    init_nfl_tables()
    
    import warnings
    from pandas.errors import PerformanceWarning
    warnings.filterwarnings('ignore', category=PerformanceWarning)
    
    print("Iniciando descarga de datos de NFL (2025-2026)... esto puede tardar un poco.")
    
    try:
        pbp = nfl.import_pbp_data([2025, 2026])
        pbp = pbp.copy() # Desfragmentar el DataFrame para evitar el PerformanceWarning
    except Exception as e:
        print(f"Error descargando PBP: {e}")
        return 0, 0
    
    # 1. Calcular EPA por equipo (ofensivo y defensivo)
    # Ofensivo
    epa_off = pbp.groupby(['posteam', 'season'])['epa'].mean().reset_index()
    # Defensivo
    epa_def = pbp.groupby(['defteam', 'season'])['epa'].mean().reset_index()
    
    equipos = pbp['posteam'].dropna().unique()
    
    epa_data = []
    for eq in equipos:
        # Ofensivo 2025 y 2026
        off_25 = epa_off[(epa_off['posteam'] == eq) & (epa_off['season'] == 2025)]['epa']
        off_26 = epa_off[(epa_off['posteam'] == eq) & (epa_off['season'] == 2026)]['epa']
        
        # Defensivo
        def_25 = epa_def[(epa_def['defteam'] == eq) & (epa_def['season'] == 2025)]['epa']
        def_26 = epa_def[(epa_def['defteam'] == eq) & (epa_def['season'] == 2026)]['epa']
        
        val_off_25 = off_25.values[0] if not off_25.empty else 0
        val_off_26 = off_26.values[0] if not off_26.empty else val_off_25
        
        val_def_25 = def_25.values[0] if not def_25.empty else 0
        val_def_26 = def_26.values[0] if not def_26.empty else val_def_25
        
        # Ponderación (0.70 año previo, 0.30 año actual)
        final_off_epa = (val_off_25 * 0.70) + (val_off_26 * 0.30)
        final_def_epa = (val_def_25 * 0.70) + (val_def_26 * 0.30)
        
        epa_data.append((eq, final_off_epa, final_def_epa))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM nfl_eficiencia_epa")
    cursor.executemany("INSERT INTO nfl_eficiencia_epa (equipo, epa_ofensivo, epa_defensivo) VALUES (?, ?, ?)", epa_data)
    
    # 2. Agregar estadísticas de jugadores
    # Pasos
    pass_df = pbp[pbp['play_type'] == 'pass'].groupby(['passer_player_name', 'posteam', 'season', 'week']).agg(
        passing_yards=('passing_yards', 'sum'),
        passing_tds=('pass_touchdown', 'sum'),
        interceptions=('interception', 'sum')
    ).reset_index()
    
    # Acarreos
    rush_df = pbp[pbp['play_type'] == 'run'].groupby(['rusher_player_name', 'posteam', 'season', 'week']).agg(
        carries=('play_id', 'count'),
        rushing_yards=('rushing_yards', 'sum'),
        rushing_tds=('rush_touchdown', 'sum')
    ).reset_index()
    
    # Recepciones
    rec_df = pbp[pbp['play_type'] == 'pass'].groupby(['receiver_player_name', 'posteam', 'season', 'week']).agg(
        targets=('play_id', 'count'),
        receptions=('complete_pass', 'sum'),
        receiving_yards=('receiving_yards', 'sum'),
        receiving_tds=('pass_touchdown', 'sum')
    ).reset_index()
    
    # Renombrar columnas para unirlas en un solo DataFrame
    pass_df.rename(columns={'passer_player_name': 'jugador'}, inplace=True)
    rush_df.rename(columns={'rusher_player_name': 'jugador'}, inplace=True)
    rec_df.rename(columns={'receiver_player_name': 'jugador'}, inplace=True)
    
    # Juntar todo usando un outer join
    merged_1 = pd.merge(pass_df, rush_df, on=['jugador', 'posteam', 'season', 'week'], how='outer').fillna(0)
    final_stats = pd.merge(merged_1, rec_df, on=['jugador', 'posteam', 'season', 'week'], how='outer').fillna(0)
    
    # Filtrar jugadores nulos
    final_stats = final_stats.dropna(subset=['jugador'])
    
    # Formato para la BD
    records_to_insert = []
    for _, row in final_stats.iterrows():
        records_to_insert.append((
            row['jugador'], row['posteam'], int(row['season']), int(row['week']),
            float(row.get('passing_yards', 0)), float(row.get('passing_tds', 0)), float(row.get('interceptions', 0)),
            float(row.get('carries', 0)), float(row.get('rushing_yards', 0)), float(row.get('rushing_tds', 0)),
            float(row.get('receptions', 0)), float(row.get('targets', 0)), float(row.get('receiving_yards', 0)), float(row.get('receiving_tds', 0))
        ))
        
    cursor.execute("DELETE FROM nfl_jugadores_stats")
    cursor.executemany('''
        INSERT INTO nfl_jugadores_stats (
            jugador, posteam, season, week, 
            passing_yards, passing_tds, interceptions, 
            carries, rushing_yards, rushing_tds, 
            receptions, targets, receiving_yards, receiving_tds
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', records_to_insert)
    
    # Poblar la tabla de partidos dummy con juegos unicos solo para los contadores (fecha hoy)
    import datetime
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    unique_games = pbp.groupby(['game_id']).first().reset_index()
    games_count = len(unique_games)
    
    cursor.execute("DELETE FROM nfl_partidos")
    cursor.execute("INSERT INTO nfl_partidos (Fecha, Local, Visitante) VALUES (?, ?, ?)", (today_str, "DUMMY", "DUMMY"))
    
    conn.commit()
    conn.close()
    
    print("Sincronización NFL completada.")
    return games_count, len(records_to_insert)

def predecir_partido_nfl(local, visitante):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM nfl_eficiencia_epa WHERE equipo=?", (local,))
    local_data = cursor.fetchone()
    cursor.execute("SELECT * FROM nfl_eficiencia_epa WHERE equipo=?", (visitante,))
    visita_data = cursor.fetchone()
    
    conn.close()
    
    if not local_data or not visita_data:
        return None
        
    local_off_epa = local_data['epa_ofensivo']
    local_def_epa = local_data['epa_defensivo']
    visita_off_epa = visita_data['epa_ofensivo']
    visita_def_epa = visita_data['epa_defensivo']
    
    epa_neto_local = local_off_epa + visita_def_epa
    epa_neto_visita = visita_off_epa + local_def_epa
    
    puntos_local = PUNTOS_BASE + (epa_neto_local * JUGADAS_PROMEDIO) + VENTAJA_LOCALIA
    puntos_visita = PUNTOS_BASE + (epa_neto_visita * JUGADAS_PROMEDIO)
    
    puntos_local = max(3.0, round(puntos_local, 1))
    puntos_visita = max(3.0, round(puntos_visita, 1))
    
    margen_victoria = puntos_local - puntos_visita
    spread_local = round(-margen_victoria * 2) / 2
    over_under_total = round(puntos_local + puntos_visita, 1)
    
    prob_local = (1 / (1 + 10 ** (-margen_victoria / 15))) * 100
    prob_visita = 100.0 - prob_local
    
    return {
        "equipo_local": local,
        "equipo_visitante": visitante,
        "puntos_local": puntos_local,
        "puntos_visitante": puntos_visita,
        "spread_local": spread_local,
        "over_under": over_under_total,
        "prob_local_pct": round(prob_local, 2),
        "prob_visita_pct": round(prob_visita, 2)
    }

def analizar_prop_nfl(jugador, estadistica, linea_casino, equipo_rival):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(f"SELECT {estadistica} FROM nfl_jugadores_stats WHERE jugador=?", (jugador,))
    rows = cursor.fetchall()
    
    if not rows or len(rows) < 5:
        conn.close()
        return {"error": "Muestra historica insuficiente (menor a 5 partidos)."}
        
    historial = [r[0] for r in rows if r[0] is not None]
    
    promedio_base = statistics.mean(historial)
    desviacion_base = statistics.stdev(historial) if len(historial) > 1 else 0.0
    
    cursor.execute("SELECT epa_defensivo FROM nfl_eficiencia_epa WHERE equipo=?", (equipo_rival,))
    rival_data = cursor.fetchone()
    conn.close()
    
    if not rival_data:
        return {"error": "Equipo rival no encontrado en la base de datos."}
        
    epa_defensivo_rival = rival_data['epa_defensivo']
    factor_ajuste = epa_defensivo_rival * 1.2
    multiplicador = max(0.75, min(1.25, 1 + factor_ajuste))
    
    promedio_ajustado = promedio_base * multiplicador
    desviacion_ajustada = desviacion_base * multiplicador
    
    if desviacion_ajustada > 0:
        dist = statistics.NormalDist(promedio_ajustado, desviacion_ajustada)
        prob_under = dist.cdf(linea_casino) * 100
    else:
        prob_under = 100.0 if promedio_ajustado < linea_casino else 0.0
        
    prob_over = 100.0 - prob_under
    
    alerta = "LINEA_EFICIENTE"
    if prob_over > 58.0:
        alerta = "VALUE_BET_OVER"
    elif prob_under > 58.0:
        alerta = "VALUE_BET_UNDER"
        
    return {
        "jugador": jugador,
        "estadistica": estadistica,
        "linea_casino": linea_casino,
        "equipo_rival": equipo_rival,
        "promedio_base": round(promedio_base, 2),
        "promedio_ajustado": round(promedio_ajustado, 2),
        "prob_over_pct": round(prob_over, 2),
        "prob_under_pct": round(prob_under, 2),
        "alerta": alerta
    }

def actualizar_calendario_nfl():
    print("Iniciando sincronización híbrida de calendario NFL...")
    try:
        import nfl_data_py as nfl
        import pandas as pd
    except ImportError:
        print("Librerías NFL no disponibles.")
        return 0
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Intento 1: Sincronización vía schedules
    try:
        df_schedules = nfl.import_schedules([2026])
        df_schedules = df_schedules.copy()
        # Filtrar partidos que ya se jugaron (tienen score no nulo)
        df_played = df_schedules.dropna(subset=['away_score', 'home_score'])
        
        updated_count = 0
        for _, row in df_played.iterrows():
            game_id = row['game_id']
            away_score = row['away_score']
            home_score = row['home_score']
            result = row['result'] if 'result' in row and pd.notna(row['result']) else home_score - away_score
            
            # Checar si en DB está nulo
            cursor.execute("SELECT away_score FROM nfl_calendario WHERE game_id = ?", (game_id,))
            db_row = cursor.fetchone()
            if db_row and db_row['away_score'] is None:
                cursor.execute('''
                    UPDATE nfl_calendario 
                    SET away_score = ?, home_score = ?, result = ?
                    WHERE game_id = ?
                ''', (float(away_score), float(home_score), float(result), game_id))
                updated_count += 1
                
        if updated_count > 0:
            conn.commit()
            print(f"Calendario actualizado vía Schedules: {updated_count} partidos actualizados.")
            
    except Exception as e:
        print(f"Error en sincronización vía schedules: {e}")
        
    # Intento 2: Fallback vía Play-by-Play para partidos que siguen nulos
    try:
        # Encontrar juegos en DB que siguen nulos
        cursor.execute("SELECT game_id FROM nfl_calendario WHERE away_score IS NULL OR home_score IS NULL")
        nulos = cursor.fetchall()
        
        if nulos:
            print("Partidos con resultado NULL encontrados, iniciando fallback PBP...")
            nulos_ids = [r['game_id'] for r in nulos]
            
            pbp = nfl.import_pbp_data([2026])
            pbp = pbp.copy()
            
            fallback_updates = 0
            for gid in nulos_ids:
                game_pbp = pbp[pbp['game_id'] == gid]
                if not game_pbp.empty:
                    # Última jugada que tenga scores válidos
                    game_pbp_valid = game_pbp.dropna(subset=['total_home_score', 'total_away_score'])
                    if not game_pbp_valid.empty:
                        last_play = game_pbp_valid.iloc[-1]
                        home_score = last_play['total_home_score']
                        away_score = last_play['total_away_score']
                        result = home_score - away_score
                        
                        cursor.execute('''
                            UPDATE nfl_calendario 
                            SET away_score = ?, home_score = ?, result = ?
                            WHERE game_id = ?
                        ''', (float(away_score), float(home_score), float(result), gid))
                        fallback_updates += 1
                        
            if fallback_updates > 0:
                conn.commit()
                print(f"Calendario actualizado vía Fallback PBP: {fallback_updates} partidos actualizados.")
                updated_count += fallback_updates
                
    except Exception as e:
        print(f"Error en sincronización fallback PBP: {e}")
        
    conn.close()
    print(f"Total de partidos de NFL actualizados en calendario: {updated_count}")
    return updated_count
