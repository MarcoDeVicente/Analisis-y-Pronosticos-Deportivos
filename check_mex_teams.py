import sqlite3
import pandas as pd

# Load CSV
df_csv = pd.read_csv('datos_crudos/MEX.csv')
csv_teams = set(df_csv['Home'].unique()) | set(df_csv['Away'].unique())

# Load DB Teams
conn = sqlite3.connect('DB-Fut-Beis.db')
df_db = pd.read_sql("SELECT Equipo_ID, Nombre FROM futbol_equipos WHERE Liga='Liga MX'", conn)
db_teams = set(df_db['Nombre'].unique())

print("Teams in CSV:")
print(sorted(list(csv_teams)))
print("\nTeams in DB:")
print(sorted(list(db_teams)))

# Find exact matches
exact_matches = csv_teams.intersection(db_teams)
print("\nExact matches:", len(exact_matches))

# Find mismatches
unmatched_csv = csv_teams - db_teams
print("\nUnmatched in CSV:")
print(sorted(list(unmatched_csv)))

# Find latest date in DB for Liga MX
query_latest = """
SELECT MAX(Fecha) FROM futbol_partidos fp
JOIN futbol_equipos fe ON fp.Local_ID = fe.Equipo_ID
WHERE fe.Liga = 'Liga MX'
"""
cursor = conn.cursor()
cursor.execute(query_latest)
latest_date = cursor.fetchone()[0]
print(f"\nLatest match date in DB for Liga MX: {latest_date}")
