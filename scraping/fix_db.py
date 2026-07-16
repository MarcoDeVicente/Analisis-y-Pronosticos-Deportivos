import sqlite3

def fix_congo():
    conn = sqlite3.connect('DB-Fut-Beis.db')
    cursor = conn.cursor()

    # Get IDs
    cursor.execute("SELECT Equipo_ID FROM futbol_equipos WHERE Nombre = 'D.R. Congo'")
    row = cursor.fetchone()
    dr_congo_id = row[0] if row else None

    cursor.execute("SELECT Equipo_ID FROM futbol_equipos WHERE Nombre = 'DR Congo'")
    row2 = cursor.fetchone()
    dr_congo_dup_id = row2[0] if row2 else None

    if dr_congo_id and dr_congo_dup_id:
        # Update partidos
        cursor.execute("UPDATE futbol_partidos SET Local_ID = ? WHERE Local_ID = ?", (dr_congo_id, dr_congo_dup_id))
        cursor.execute("UPDATE futbol_partidos SET Visitante_ID = ? WHERE Visitante_ID = ?", (dr_congo_id, dr_congo_dup_id))
        
        # Update stats
        cursor.execute("UPDATE futbol_estadisticas SET Equipo_ID = ? WHERE Equipo_ID = ?", (dr_congo_id, dr_congo_dup_id))
        
        # Delete duplicate team
        cursor.execute("DELETE FROM futbol_equipos WHERE Equipo_ID = ?", (dr_congo_dup_id,))
        
        conn.commit()
        print("Merged 'DR Congo' into 'D.R. Congo'")
    else:
        print("No duplicate DR Congo found or missing original.")

    conn.close()

if __name__ == '__main__':
    fix_congo()
