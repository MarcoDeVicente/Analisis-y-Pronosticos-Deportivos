import nfl_data_py as nfl
import sqlite3
import pandas as pd

def fabricar_props_desde_jugadas():
    print("🏈 Esquivando el Error 404...")
    print("🧠 Construyendo estadísticas de jugadores directamente desde el Play-by-Play (2025-2026)")
    
    try:
        # 1. Descargamos la data cruda que SABEMOS que sí funciona
        print("📡 Descargando jugadas... (Esto tomará un minuto)")
        df_pbp = nfl.import_pbp_data([2025, 2026])
        
        print("🧮 Procesando y sumando estadísticas por jugador...")
        
        # --- 2. MERCADO DE QUARTERBACKS (PASES) ---
        # Filtramos pases y agrupamos por el nombre del lanzador
        pases = df_pbp[df_pbp['play_type'] == 'pass'].groupby(
            ['passer_player_name', 'posteam', 'season', 'week']
        ).agg(
            passing_yards=('passing_yards', 'sum'),
            passing_tds=('pass_touchdown', 'sum'),
            interceptions=('interception', 'sum'),
            attempts=('play_id', 'count'),
            completions=('complete_pass', 'sum')
        ).reset_index().rename(columns={'passer_player_name': 'jugador'})

        # --- 3. MERCADO DE CORREDORES (ACARREOS) ---
        acarreos = df_pbp[df_pbp['play_type'] == 'run'].groupby(
            ['rusher_player_name', 'posteam', 'season', 'week']
        ).agg(
            rushing_yards=('rushing_yards', 'sum'),
            rushing_tds=('rush_touchdown', 'sum'),
            carries=('play_id', 'count')
        ).reset_index().rename(columns={'rusher_player_name': 'jugador'})

        # --- 4. MERCADO DE RECEPTORES (RECEPCIONES) ---
        recepciones = df_pbp[df_pbp['play_type'] == 'pass'].groupby(
            ['receiver_player_name', 'posteam', 'season', 'week']
        ).agg(
            receiving_yards=('receiving_yards', 'sum'),
            receiving_tds=('pass_touchdown', 'sum'),
            receptions=('complete_pass', 'sum'),
            targets=('play_id', 'count')  # Cuántas veces le lanzaron el balón
        ).reset_index().rename(columns={'receiver_player_name': 'jugador'})

        print("🔗 Fusionando mercados en una sola tabla matriz...")
        # Unimos las tres tablas usando el nombre del jugador, equipo, año y semana
        df_props = pd.merge(pases, acarreos, on=['jugador', 'posteam', 'season', 'week'], how='outer')
        df_props = pd.merge(df_props, recepciones, on=['jugador', 'posteam', 'season', 'week'], how='outer')
        
        # Limpiamos los nulos (ej. Un receptor puro tendrá NaN en passing_yards, lo pasamos a 0)
        df_props.fillna(0, inplace=True)
        
        # Eliminamos filas donde el nombre del jugador esté vacío (jugadas rotas/castigos)
        df_props = df_props.dropna(subset=['jugador'])

        # --- PRUEBA EN CONSOLA ---
        print("\n🔥 Ejemplo de Datos Construidos (Lamar Jackson - 2025):")
        lamar = df_props[(df_props['jugador'] == 'L.Jackson') & (df_props['season'] == 2025)]
        print(lamar[['week', 'passing_yards', 'rushing_yards', 'passing_tds', 'rushing_tds']].head().to_string(index=False))

        # --- GUARDAR EN SQLITE ---
        print("\n💾 Guardando tu propia tabla de Player Props en DB-NFL-Test.db...")
        conexion = sqlite3.connect("DB-NFL-Test.db")
        df_props.to_sql('nfl_jugadores_stats', conexion, if_exists='replace', index=False)
        conexion.close()
        
        print("✅ ¡Misión Cumplida! Tienes los datos más actualizados sin depender del servidor semanal.")

    except Exception as e:
        print(f"⚠️ Error durante la construcción: {e}")

if __name__ == "__main__":
    fabricar_props_desde_jugadas()