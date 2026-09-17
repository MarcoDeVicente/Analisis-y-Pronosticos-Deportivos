import sqlite3, pandas as pd

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
    match = next((name for name in db_names if name == v or (k == 'Alaves' and 'Alav' in name) or (k == 'Espanol' and 'Espanyol' in name)), None)
    if match: equipo_id_map[k] = df_equipos[df_equipos['Nombre'] == match]['Equipo_ID'].values[0]

df_csv = pd.read_csv('datos_crudos/SP1.csv')
df_csv['Date_dt'] = pd.to_datetime(df_csv['Date'], format='%d/%m/%Y')
df_csv['Fecha'] = df_csv['Date_dt'].dt.strftime('%Y-%m-%d')
df_csv['Local_ID'] = df_csv['HomeTeam'].map(equipo_id_map)
df_csv['Visitante_ID'] = df_csv['AwayTeam'].map(equipo_id_map)

df_partidos = pd.read_sql("SELECT Fecha, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante FROM futbol_partidos", conn)

merged = pd.merge(df_csv, df_partidos, on=['Fecha', 'Local_ID', 'Visitante_ID'], how='left', indicator=True)
missing = merged[merged['_merge'] == 'left_only']

if len(missing) > 0:
    print(f"There are {len(missing)} matches missing in the DB.")
else:
    print("All 380 matches from SP1.csv are present in the DB.")
    
    # Check for discrepancies in goals
    discrepancies = merged[(merged['FTHG'] != merged['Goles_Local']) | (merged['FTAG'] != merged['Goles_Visitante'])]
    if len(discrepancies) > 0:
        print(f"Found {len(discrepancies)} matches with different scores:")
        print(discrepancies[['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'Goles_Local', 'FTAG', 'Goles_Visitante']].head())
    else:
        print("All match scores match perfectly between the CSV and the DB.")
