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
    match = next((name for name in db_names if v.replace('é', '') in name or name.startswith(v[:5])), None)
    if not match: match = next((name for name in db_names if k in name), None)
    if match: 
        equipo_id_map[k] = df_equipos[df_equipos['Nombre'] == match]['Equipo_ID'].values[0]
        print(f"{k} mapped to {match} (ID: {equipo_id_map[k]})")

ids = list(equipo_id_map.values())
if len(ids) != len(set(ids)):
    print("Duplicate IDs found in mapping!")
else:
    print("All IDs are unique.")
