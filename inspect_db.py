import sqlite3

def check_db():
    conn = sqlite3.connect('DB-Fut-Beis.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:")
    for table in tables:
        print(f"  - {table[0]}")
        cursor.execute(f"PRAGMA table_info('{table[0]}');")
        columns = cursor.fetchall()
        for col in columns:
            print(f"    {col[1]} ({col[2]})")
            
if __name__ == '__main__':
    check_db()
