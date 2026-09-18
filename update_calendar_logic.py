import os

with open('nfl_logic.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Add the new function at the end
new_function = """
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
"""

if "def actualizar_calendario_nfl" not in code:
    code += new_function

# Now we need to call it inside sincronizar_datos_nfl
# We will place the call right before "print('Sincronización NFL completada.')"
call_code = """
    # Actualizar calendario hibrido
    actualizar_calendario_nfl()
    
    print("Sincronización NFL completada.")"""

if "actualizar_calendario_nfl()" not in code:
    code = code.replace('print("Sincronización NFL completada.")', call_code)

with open('nfl_logic.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("nfl_logic.py updated with actualizar_calendario_nfl")
