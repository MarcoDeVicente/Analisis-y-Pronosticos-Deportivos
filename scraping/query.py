import sqlite3
import pandas as pd

conn = sqlite3.connect('DB-Fut-Beis.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM futbol_equipos WHERE Nombre LIKE '%Congo%'")
rows = cursor.fetchall()
print("futbol_equipos:", rows)

cursor.execute("SELECT * FROM futbol_partidos WHERE Local_ID IN (SELECT Equipo_ID FROM futbol_equipos WHERE Nombre LIKE '%Congo%') OR Visitante_ID IN (SELECT Equipo_ID FROM futbol_equipos WHERE Nombre LIKE '%Congo%')")
print("partidos with Congo:", len(cursor.fetchall()))
