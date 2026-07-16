import sqlite3
import pandas as pd

conn = sqlite3.connect('DB-Fut-Beis.db')
df = pd.read_sql_query("SELECT Nombre, Liga FROM futbol_equipos", conn)
with open('teams.txt', 'w', encoding='utf-8') as f:
    f.write(df.to_string())
conn.close()
