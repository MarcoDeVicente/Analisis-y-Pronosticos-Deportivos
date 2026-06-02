import sqlite3
import pandas as pd
import numpy as np

def calcular_forma_pitchers(db_path='DB-Fut-Beis.db', salidas_recientes=3):
    print("Conectando a SQLite y extrayendo el historico de pitcheo...")
    conexion = sqlite3.connect(db_path)
    
    # Extraemos a los pitchers, uniendo los datos con la tabla de partidos para tener la Fecha
    query = '''
        SELECT 
            p.Fecha, p.Partido_ID, j.Nombre_Completo as Pitcher, 
            sp.Innings_Lanzados, sp.Carreras_Limpias, sp.Ponches
        FROM beisbol_stats_pitcheo sp
        JOIN beisbol_partidos p ON sp.Partido_ID = p.Partido_ID
        JOIN beisbol_jugadores j ON sp.Pitcher_ID = j.Jugador_ID
        WHERE sp.Innings_Lanzados >= 3.0  -- Filtro clave: Solo evaluamos a los Abridores (3+ innings)
        ORDER BY j.Nombre_Completo, p.Fecha ASC
    '''
    df_pitchers = pd.read_sql_query(query, conexion)
    conexion.close()

    # 1. Aseguramos el formato de fecha correcto cronológicamente
    df_pitchers['Fecha'] = pd.to_datetime(df_pitchers['Fecha'])
    
    print(f"Calculando metricas avanzadas (ERA y Ponches) de las ultimas {salidas_recientes} aperturas...")

    # 2. Ordenamos estrictamente por Pitcher y luego por Fecha
    df_pitchers = df_pitchers.sort_values(by=['Pitcher', 'Fecha'])

    # 3. Operaciones Vectorizadas (Acumulando estadísticas recientes desplazadas)
    # Sumamos los Innings y Carreras de los últimos juegos
    df_pitchers['IP_Acumulado'] = df_pitchers.groupby('Pitcher')['Innings_Lanzados'].transform(
        lambda x: x.rolling(window=salidas_recientes, min_periods=1).sum().shift(1)
    )
    df_pitchers['CL_Acumuladas'] = df_pitchers.groupby('Pitcher')['Carreras_Limpias'].transform(
        lambda x: x.rolling(window=salidas_recientes, min_periods=1).sum().shift(1)
    )
    # Promediamos los Ponches de los últimos juegos
    df_pitchers['Ponches_Prom_Reciente'] = df_pitchers.groupby('Pitcher')['Ponches'].transform(
        lambda x: x.rolling(window=salidas_recientes, min_periods=1).mean().shift(1)
    )

    # 4. Cálculo de la Métrica Reina: ERA (Earned Run Average)
    # Si IP_Acumulado es mayor a 0, hacemos la fórmula, si no, lo dejamos en 0 para evitar errores matemáticos
    df_pitchers['ERA_Reciente'] = np.where(
        df_pitchers['IP_Acumulado'] > 0,
        (df_pitchers['CL_Acumuladas'] * 9) / df_pitchers['IP_Acumulado'],
        0.0
    )
    
    df_pitchers['ERA_Reciente'] = df_pitchers['ERA_Reciente'].round(2)
    df_pitchers['Ponches_Prom_Reciente'] = df_pitchers['Ponches_Prom_Reciente'].fillna(0.0).round(1)

    # Eliminamos las filas donde no hay historial previo (la primera salida de cada pitcher)
    df_pitchers = df_pitchers.dropna(subset=['IP_Acumulado'])

    print("\n--- Estado de Forma Reciente: ABRIDORES ---")
    print(df_pitchers[['Fecha', 'Pitcher', 'Innings_Lanzados', 'Carreras_Limpias', 'ERA_Reciente', 'Ponches_Prom_Reciente']].tail(10))
    
    return df_pitchers


df_features = calcular_forma_pitchers()