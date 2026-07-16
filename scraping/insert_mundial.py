import sqlite3
import pandas as pd
from datetime import datetime, timezone

def main():
    conn = sqlite3.connect('DB-Fut-Beis.db')
    cursor = conn.cursor()

    df = pd.read_csv('international-world-cup-matches-2026-to-2026-stats.csv')
    df_complete = df[df['status'] == 'complete']

    team_map = {
        'Curaçao': 'Curacao',
        'USMNT': 'USA',
        'Cape Verde Islands': 'Cape Verde',
        'Bosnia and Herzegovina': 'Bosnia & Herzegovina',
        'Congo DR': 'D.R. Congo'
    }

    df_complete['home_team_name'] = df_complete['home_team_name'].replace(team_map)
    df_complete['away_team_name'] = df_complete['away_team_name'].replace(team_map)

    # Fetch all teams from DB
    cursor.execute("SELECT Equipo_ID, Nombre FROM futbol_equipos")
    db_teams = {name: eq_id for eq_id, name in cursor.fetchall()}

    for index, row in df_complete.iterrows():
        home_team = row['home_team_name']
        away_team = row['away_team_name']

        if home_team not in db_teams:
            print(f"Warning: Team {home_team} not found in DB.")
            continue
        if away_team not in db_teams:
            print(f"Warning: Team {away_team} not found in DB.")
            continue

        home_id = db_teams[home_team]
        away_id = db_teams[away_team]

        fecha_ts = int(row['timestamp'])
        fecha = datetime.fromtimestamp(fecha_ts, tz=timezone.utc).strftime('%Y-%m-%d')
        
        # Check if match already exists
        cursor.execute('''SELECT Partido_ID FROM futbol_partidos 
                          WHERE Fecha = ? AND Local_ID = ? AND Visitante_ID = ?''', 
                       (fecha, home_id, away_id))
        match = cursor.fetchone()
        
        if match:
            print(f"Match {home_team} vs {away_team} on {fecha} already exists. Skipping.")
            continue

        # Insert Partido
        cursor.execute('''
            INSERT INTO futbol_partidos (Fecha, Temporada, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante, Cuota_Local, Cuota_Empate, Cuota_Visitante)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            fecha, "2026", home_id, away_id, 
            int(row['home_team_goal_count']), int(row['away_team_goal_count']),
            float(row['odds_ft_home_team_win']), float(row['odds_ft_draw']), float(row['odds_ft_away_team_win'])
        ))
        
        partido_id = cursor.lastrowid
        print(f"Inserted match: {home_team} vs {away_team} on {fecha} with ID {partido_id}")

        # Insert Estadisticas Local
        cursor.execute('''
            INSERT INTO futbol_estadisticas (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            partido_id, home_id, 1,
            int(row['home_team_shots']), int(row['home_team_shots_on_target']),
            int(row['home_team_fouls']), int(row['home_team_corner_count']),
            int(row['home_team_yellow_cards']), int(row['home_team_red_cards']), float(row['team_a_xg'])
        ))

        # Insert Estadisticas Visitante
        cursor.execute('''
            INSERT INTO futbol_estadisticas (Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas, xG)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            partido_id, away_id, 0,
            int(row['away_team_shots']), int(row['away_team_shots_on_target']),
            int(row['away_team_fouls']), int(row['away_team_corner_count']),
            int(row['away_team_yellow_cards']), int(row['away_team_red_cards']), float(row['team_b_xg'])
        ))

    conn.commit()
    conn.close()
    print("Done inserting completed matches.")

if __name__ == '__main__':
    main()
