import sqlite3

conn = sqlite3.connect('DB-Fut-Beis.db')
cursor = conn.cursor()
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='nfl_calendario'")
row = cursor.fetchone()
if row:
    print(row[0])
else:
    print("Table does not exist")
conn.close()
