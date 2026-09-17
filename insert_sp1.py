import sqlite3, pandas as pd
import numpy as np

mapping = {
    'Alaves': 'Deportivo Alavés', 'Ath Bilbao': 'Athletic Bilbao', 'Ath Madrid': 'Atletico Madrid',
    'Barcelona': 'Barcelona', 'Betis': 'Real Betis', 'Celta': 'RC Celta de Vigo', 'Elche': 'Elche',
    'Espanol': 'RCD Espanyol de Barcelona', 'Getafe': 'Getafe', 'Girona': 'Girona', 'Levante': 'Levante',
    'Mallorca': 'RCD Mallorca', 'Osasuna': 'CA Osasuna', 'Oviedo': 'Real Oviedo', 'Real Madrid': 'Real Madrid',
    'Sevilla': 'Sevilla', 'Sociedad': 'Real Sociedad', 'Valencia': 'Valencia', 'Vallecano': 'Rayo Vallecano de Madrid',
    'Villarreal': 'Villarreal'
}

conn = sqlite3.connect('DB-Fut-Beis.db')
df_equipos = pd.read_sql("SELECT Equipo_ID, Nombre FROM futbol_equipos WHERE Liga='La Liga'", conn)
db_names = df_equipos['Nombre'].tolist()

equipo_id_map = {}
for k, v in mapping.items():
    # Because of encoding issues, let's match exact except for 'Alaves'
    match = next((name for name in db_names if name == v or (k == 'Alaves' and 'Alav' in name) or (k == 'Espanol' and 'Espanyol' in name)), None)
    if match: 
        equipo_id_map[k] = df_equipos[df_equipos['Nombre'] == match]['Equipo_ID'].values[0]
    else:
        print(f"FAILED TO MAP: {k} -> {v}")

df_csv = pd.read_csv('datos_crudos/SP1.csv')
df_csv['Date_dt'] = pd.to_datetime(df_csv['Date'], format='%d/%m/%Y')
df_csv['Fecha'] = df_csv['Date_dt'].dt.strftime('%Y-%m-%d')
df_csv['Local_ID'] = df_csv['HomeTeam'].map(equipo_id_map)
df_csv['Visitante_ID'] = df_csv['AwayTeam'].map(equipo_id_map)

df_partidos = pd.read_sql("SELECT Fecha, Local_ID, Visitante_ID FROM futbol_partidos", conn)

merged = pd.merge(df_csv, df_partidos, on=['Fecha', 'Local_ID', 'Visitante_ID'], how='left', indicator=True)
missing = merged[merged['_merge'] == 'left_only'].copy()

print(f"Adding {len(missing)} missing matches...")

cursor = conn.cursor()
for index, row in missing.iterrows():
    cursor.execute('''
        INSERT INTO futbol_partidos (
            Fecha, Temporada, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante,
            Cuota_Local, Cuota_Empate, Cuota_Visitante, MaxCH, MaxCD, MaxCA, AvgCH, AvgCD, AvgCA
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        row['Fecha'], '2025', int(row['Local_ID']), int(row['Visitante_ID']), int(row['FTHG']), int(row['FTAG']),
        row.get('B365H') if pd.notna(row.get('B365H')) else (row.get('AvgH') if pd.notna(row.get('AvgH')) else None),
        row.get('B365D') if pd.notna(row.get('B365D')) else (row.get('AvgD') if pd.notna(row.get('AvgD')) else None),
        row.get('B365A') if pd.notna(row.get('B365A')) else (row.get('AvgA') if pd.notna(row.get('AvgA')) else None),
        row.get('MaxCH') if pd.notna(row.get('MaxCH')) else None,
        row.get('MaxCD') if pd.notna(row.get('MaxCD')) else None,
        row.get('MaxCA') if pd.notna(row.get('MaxCA')) else None,
        row.get('AvgCH') if pd.notna(row.get('AvgCH')) else None,
        row.get('AvgCD') if pd.notna(row.get('AvgCD')) else None,
        row.get('AvgCA') if pd.notna(row.get('AvgCA')) else None
    ))
    
    partido_id = cursor.lastrowid
    
    cursor.execute('''
        INSERT INTO futbol_estadisticas (
            Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        partido_id, int(row['Local_ID']), 1,
        int(row['HS']) if pd.notna(row.get('HS')) else 0,
        int(row['HST']) if pd.notna(row.get('HST')) else 0,
        int(row['HF']) if pd.notna(row.get('HF')) else 0,
        int(row['HC']) if pd.notna(row.get('HC')) else 0,
        int(row['HY']) if pd.notna(row.get('HY')) else 0,
        int(row['HR']) if pd.notna(row.get('HR')) else 0
    ))
    
    cursor.execute('''
        INSERT INTO futbol_estadisticas (
            Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        partido_id, int(row['Visitante_ID']), 0,
        int(row['AS']) if pd.notna(row.get('AS')) else 0,
        int(row['AST']) if pd.notna(row.get('AST')) else 0,
        int(row['AF']) if pd.notna(row.get('AF')) else 0,
        int(row['AC']) if pd.notna(row.get('AC')) else 0,
        int(row['AY']) if pd.notna(row.get('AY')) else 0,
        int(row['AR']) if pd.notna(row.get('AR')) else 0
    ))

conn.commit()
print("Insertion complete.")
