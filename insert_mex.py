import sqlite3
import pandas as pd
import numpy as np

# Conectar a la base de datos
conn = sqlite3.connect('DB-Fut-Beis.db')

# Cargar CSV
df_csv = pd.read_csv('datos_crudos/MEX.csv')

# Formatear la fecha a YYYY-MM-DD
df_csv['Date_dt'] = pd.to_datetime(df_csv['Date'], format='%d/%m/%Y')
df_csv['Fecha'] = df_csv['Date_dt'].dt.strftime('%Y-%m-%d')

# Cargar ID de equipos
df_equipos = pd.read_sql("SELECT Equipo_ID, Nombre FROM futbol_equipos WHERE Liga='Liga MX'", conn)
equipo_map = dict(zip(df_equipos['Nombre'], df_equipos['Equipo_ID']))

# Mapear nombres del CSV a Equipo_ID
df_csv['Local_ID'] = df_csv['Home'].map(equipo_map)
df_csv['Visitante_ID'] = df_csv['Away'].map(equipo_map)

# Extraer el primer año de la temporada, e.g. "2026/2027" -> "2026"
# In some databases Temporada is just "2026". We will take the first 4 characters.
df_csv['Temporada_Year'] = df_csv['Season'].apply(lambda x: str(x).split('/')[0] if pd.notna(x) else None)

# Cargar los partidos existentes de Liga MX para no duplicar
df_partidos = pd.read_sql("""
    SELECT Fecha, Local_ID, Visitante_ID 
    FROM futbol_partidos 
    WHERE Local_ID IN (SELECT Equipo_ID FROM futbol_equipos WHERE Liga='Liga MX')
""", conn)

# Identificar los partidos faltantes
merged = pd.merge(df_csv, df_partidos, on=['Fecha', 'Local_ID', 'Visitante_ID'], how='left', indicator=True)
missing = merged[merged['_merge'] == 'left_only'].copy()

print(f"Agregando {len(missing)} partidos nuevos...")

cursor = conn.cursor()
for index, row in missing.iterrows():
    # Helper for getting valid values or None
    def get_val(col):
        if col in row and pd.notna(row[col]):
            return float(row[col])
        return None

    # Determine Cuota
    cuota_local = get_val('B365CH') or get_val('AvgCH') or get_val('PSCH')
    cuota_empate = get_val('B365CD') or get_val('AvgCD') or get_val('PSCD')
    cuota_visita = get_val('B365CA') or get_val('AvgCA') or get_val('PSCA')

    cursor.execute('''
        INSERT INTO futbol_partidos (
            Fecha, Temporada, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante,
            Cuota_Local, Cuota_Empate, Cuota_Visitante, MaxCH, MaxCD, MaxCA, AvgCH, AvgCD, AvgCA
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        row['Fecha'], str(row['Temporada_Year']), int(row['Local_ID']), int(row['Visitante_ID']), int(row['HG']), int(row['AG']),
        cuota_local, cuota_empate, cuota_visita,
        get_val('MaxCH'), get_val('MaxCD'), get_val('MaxCA'), 
        get_val('AvgCH'), get_val('AvgCD'), get_val('AvgCA')
    ))
    
    partido_id = cursor.lastrowid
    
    # Insertar stats vacios como en insert_sp1.py
    cursor.execute('''
        INSERT INTO futbol_estadisticas (
            Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        partido_id, int(row['Local_ID']), 1,
        get_val('HS') or 0, get_val('HST') or 0, get_val('HF') or 0, 
        get_val('HC') or 0, get_val('HY') or 0, get_val('HR') or 0
    ))
    
    cursor.execute('''
        INSERT INTO futbol_estadisticas (
            Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        partido_id, int(row['Visitante_ID']), 0,
        get_val('AS') or 0, get_val('AST') or 0, get_val('AF') or 0, 
        get_val('AC') or 0, get_val('AY') or 0, get_val('AR') or 0
    ))

conn.commit()
print("Insercion completada.")
