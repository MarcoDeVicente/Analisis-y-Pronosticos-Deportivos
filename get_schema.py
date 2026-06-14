import sqlite3
conn = sqlite3.connect('DB-Fut-Beis.db')
cursor = conn.cursor()
cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for name, sql in tables:
    print(f"Table: {name}")
    print(f"SQL: {sql}\n")
conn.close()
