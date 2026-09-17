import sqlite3
import pandas as pd
conn = sqlite3.connect('DB-Fut-Beis.db')
cursor = conn.cursor()
cursor.execute('PRAGMA foreign_keys')
print(cursor.fetchone())
