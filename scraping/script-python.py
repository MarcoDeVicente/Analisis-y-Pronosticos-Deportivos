import sqlite3
import pandas as pd
import math

def safe_int(row, col, default=0):
    """Obtiene un valor entero de una fila, regresando 'default' si la columna
    no existe o si el valor es NaN/None. Soluciona el problema de que pandas
    inserta NaN como NULL en SQLite en lugar de 0."""
    val = row.get(col, default)
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return default
    return int(val)

def cargar_datos_futbol(ruta_csv, nombre_db='DB-Fut-Beis.db', liga_nombre='Futbol'):
    print(f"Leyendo datos desde: {ruta_csv}")
    
    # Leemos el archivo. Si lo tienes en Excel (.xlsx), guárdalo como .csv primero
    df = pd.read_csv(ruta_csv)
    
    # 1. Limpieza inicial: Asegurarnos de que no haya filas vacías
    df = df.dropna(subset=['Home', 'Away'])
    
    # 2. Conexión a la base de datos
    conexion = sqlite3.connect(nombre_db)
    cursor = conexion.cursor()

    try:
        # --- FASE 1: ACTUALIZAR EL CATÁLOGO DE EQUIPOS ---
        equipos = pd.concat([df['Home'], df['Away']]).unique()
        
        for equipo in equipos:
            cursor.execute('''
                INSERT OR IGNORE INTO futbol_equipos (Nombre, Liga) 
                VALUES (?, ?)
            ''', (equipo, liga_nombre))
        conexion.commit()

        # --- FASE 2: MAPEAR NOMBRES A IDs ---
        df_equipos_db = pd.read_sql('SELECT Equipo_ID, Nombre FROM futbol_equipos', conexion)
        mapa_equipos = dict(zip(df_equipos_db.Nombre, df_equipos_db.Equipo_ID))

        df['Local_ID'] = df['Home'].map(mapa_equipos)
        df['Visitante_ID'] = df['Away'].map(mapa_equipos)
        
        # --- FASE 3: INSERTAR PARTIDOS Y ESTADÍSTICAS ---
        partidos_insertados = 0
        for index, row in df.iterrows():
            
            # Insertar en futbol_partidos
            cursor.execute('''
                INSERT INTO futbol_partidos 
                (Fecha, Temporada, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante, Cuota_Local, Cuota_Empate, Cuota_Visitante)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['Date'], 
                '2026', # Temporada
                row['Local_ID'], 
                row['Visitante_ID'], 
                row['HG'], 
                row['AG'], 
                None, None, None # Este archivo no tiene cuotas de apuestas
            ))
            
            partido_id = cursor.lastrowid

            # Insertar estadísticas del Local
            cursor.execute('''
                INSERT INTO futbol_estadisticas 
                (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                partido_id, 
                row['Local_ID'], 
                True,
                safe_int(row, 'HS'), 
                safe_int(row, 'HST'),  # Home Shots on Target
                safe_int(row, 'HF'),   # Faltas (puede no existir en algunos CSV)
                safe_int(row, 'HC'), 
                safe_int(row, 'HY'), 
                safe_int(row, 'HR'),
                safe_int(row, 'HxG')
            ))

            # Insertar estadísticas del Visitante
            cursor.execute('''
                INSERT INTO futbol_estadisticas 
                (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                partido_id, 
                row['Visitante_ID'], 
                False,
                safe_int(row, 'AS'), 
                safe_int(row, 'AST'),  # Away Shots on Target
                safe_int(row, 'AF'),   # Faltas (puede no existir en algunos CSV)
                safe_int(row, 'AC'), 
                safe_int(row, 'AY'), 
                safe_int(row, 'AR'),
                safe_int(row, 'AxG')
            ))
            
            partidos_insertados += 1

        conexion.commit()
        print(f"¡Éxito! Se guardaron {partidos_insertados} partidos del Futbol correctamente.")

    except Exception as e:
        conexion.rollback()
        print(f"Ocurrió un error en la inserción: {e}")
    finally:
        conexion.close()


cargar_datos_futbol('WorldCup2026-1.csv')
cargar_datos_futbol('anfitriones_stats_real.csv')
cargar_datos_futbol('F1-2.csv', liga_nombre='Ligue 1')
cargar_datos_futbol('E0-2.csv', liga_nombre='Premier League')
cargar_datos_futbol('UCL_2025_26.csv', liga_nombre='Champions League')