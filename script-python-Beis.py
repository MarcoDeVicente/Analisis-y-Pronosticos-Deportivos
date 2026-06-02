import statsapi
import sqlite3
import time

def cargar_historico_mlb(fecha_inicio, fecha_fin, nombre_db='DB-Fut-Beis.db'):
    """
    Descarga un rango de fechas completo, extrayendo resultados, jugadores y métricas (Boxscore).
    """
    print(f"Consultando la API desde {fecha_inicio} hasta {fecha_fin}...")
    
    conexion = sqlite3.connect(nombre_db)
    cursor = conexion.cursor()

    try:
        # Obtenemos todos los juegos en ese rango de fechas
        juegos = statsapi.schedule(start_date=fecha_inicio, end_date=fecha_fin)
        
        if not juegos:
            print("No se encontraron partidos en este rango de fechas.")
            return

        partidos_insertados = 0
        
        for juego in juegos:
            # Filtro estricto: Solo partidos terminados
            if juego['status'] != 'Final':
                continue

            game_pk = juego['game_id']
            local_id = juego['home_id']
            visitante_id = juego['away_id']
            
            # --- FASE 1: EQUIPOS Y PARTIDO PRINCIPAL ---
            cursor.execute('INSERT OR IGNORE INTO beisbol_equipos (Equipo_ID, Nombre, Abreviatura) VALUES (?, ?, ?)', 
                           (local_id, juego['home_name'], juego.get('home_file_code', '')))
            cursor.execute('INSERT OR IGNORE INTO beisbol_equipos (Equipo_ID, Nombre, Abreviatura) VALUES (?, ?, ?)', 
                           (visitante_id, juego['away_name'], juego.get('away_file_code', '')))

            cursor.execute('''
                INSERT OR IGNORE INTO beisbol_partidos 
                (Partido_ID, Fecha, Local_ID, Visitante_ID, Carreras_Local, Carreras_Visitante)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (game_pk, juego['game_date'], local_id, visitante_id, juego['home_score'], juego['away_score']))

            # --- FASE 2: EXTRACCIÓN DE JUGADORES Y ESTADÍSTICAS (BOXSCORE) ---
            try:
                # Esta llamada trae toda la sábana de estadísticas del partido
                caja = statsapi.boxscore_data(game_pk)
            except Exception as e:
                print(f"Error extrayendo estadísticas del juego {game_pk}: {e}")
                continue

            # 1. Guardar el catálogo de Jugadores (Nombres y Posiciones)
            for p_id, p_info in caja.get('playerInfo', {}).items():
                cursor.execute('''
                    INSERT OR IGNORE INTO beisbol_jugadores (Jugador_ID, Nombre_Completo, Posicion)
                    VALUES (?, ?, ?)
                ''', (p_info['id'], p_info['fullName'], p_info.get('primaryPosition', {}).get('abbreviation', '')))

            # 2. Extraer Estadísticas Dinámicas de Bateo y Pitcheo
            for equipo_tipo in ['home', 'away']:
                jugadores_equipo = caja.get(equipo_tipo, {}).get('players', {})

                for p_id_str, stats_data in jugadores_equipo.items():
                    if 'person' not in stats_data: 
                        continue
                    
                    jugador_id = stats_data['person']['id']

                    # --- Bateo ---
                    batting = stats_data.get('stats', {}).get('batting', {})
                    if batting and batting.get('atBats', 0) > 0:
                        cursor.execute('''
                            INSERT OR IGNORE INTO beisbol_stats_bateo 
                            (Partido_ID, Bateador_ID, Turnos_Al_Bate, Hits, Home_Runs, Carreras_Impulsadas, Ponches)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            game_pk, jugador_id,
                            batting.get('atBats', 0), batting.get('hits', 0),
                            batting.get('homeRuns', 0), batting.get('rbi', 0),
                            batting.get('strikeOuts', 0)
                        ))

                    # --- Pitcheo ---
                    pitching = stats_data.get('stats', {}).get('pitching', {})
                    if pitching and 'inningsPitched' in pitching:
                        # La API devuelve los innings como texto (ej: "5.1" o "6.0")
                        try:
                            ip = float(pitching.get('inningsPitched', '0'))
                        except ValueError:
                            ip = 0.0

                        cursor.execute('''
                            INSERT OR IGNORE INTO beisbol_stats_pitcheo 
                            (Partido_ID, Pitcher_ID, Innings_Lanzados, Hits_Permitidos, Carreras_Limpias, Bases_Por_Bolas, Ponches)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            game_pk, jugador_id, ip,
                            pitching.get('hits', 0), pitching.get('earnedRuns', 0),
                            pitching.get('baseOnBalls', 0), pitching.get('strikeOuts', 0)
                        ))

            partidos_insertados += 1
            
            # Pausa táctica para no saturar la CPU ni el servidor de la API
            time.sleep(0.5)

        conexion.commit()
        print(f"¡Proceso completo! Se guardaron {partidos_insertados} juegos y todas sus estadísticas.")

    except Exception as e:
        conexion.rollback()
        print(f"Ocurrió un error general: {e}")
    finally:
        conexion.close()

# --- EJECUCIÓN DEL SCRIPT (Rango de un mes completo) ---
# Usaremos fechas pasadas reales para garantizar que haya juegos en estado 'Final'
cargar_historico_mlb(fecha_inicio='2026-05-01', fecha_fin='2026-05-26')