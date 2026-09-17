import os
import sqlite3
import pandas as pd
from datetime import datetime
import unidecode

def normalize_name(name):
    if pd.isna(name): return ""
    name = str(name).strip()
    return unidecode.unidecode(name).lower()

def get_or_create_team(cursor, team_name, default_league):
    # Find existing team by similarity or exact match
    cursor.execute("SELECT Equipo_ID, Nombre, Liga FROM futbol_equipos")
    teams = cursor.fetchall()
    
    # Perfect match
    for row in teams:
        if row[1] == team_name:
            return row[0]
            
    # Normalized match
    norm_target = normalize_name(team_name)
    for row in teams:
        if normalize_name(row[1]) == norm_target:
            return row[0]
            
    # If not found, insert
    cursor.execute("INSERT INTO futbol_equipos (Nombre, Liga) VALUES (?, ?)", (team_name, default_league))
    return cursor.lastrowid

def insert_matches_from_csv(file_path, db_conn, league_name, is_champ_file=False, ucl_teams_norm=None):
    if not os.path.exists(file_path):
        print(f"Archivo no encontrado: {file_path}")
        return
        
    print(f"Procesando {file_path}...")
    df_csv = pd.read_csv(file_path)
    
    if 'Date' not in df_csv.columns:
        print(f"Error: columna Date no encontrada en {file_path}")
        return
        
    # Standardize date format (some might be DD/MM/YYYY, others YYYY-MM-DD)
    try:
        df_csv['Date_dt'] = pd.to_datetime(df_csv['Date'], format='%d/%m/%Y', errors='coerce')
        # If any NaT, try standard format
        mask = df_csv['Date_dt'].isna()
        if mask.any():
            df_csv.loc[mask, 'Date_dt'] = pd.to_datetime(df_csv.loc[mask, 'Date'], errors='coerce')
            
        df_csv['Fecha'] = df_csv['Date_dt'].dt.strftime('%Y-%m-%d')
    except Exception as e:
        print(f"Error parseando fechas en {file_path}: {e}")
        return
        
    df_csv = df_csv.dropna(subset=['Fecha', 'HomeTeam', 'AwayTeam'])
    
    if is_champ_file and ucl_teams_norm:
        # Filter rows where either Home or Away is a Champions team
        df_csv['Home_norm'] = df_csv['HomeTeam'].apply(normalize_name)
        df_csv['Away_norm'] = df_csv['AwayTeam'].apply(normalize_name)
        
        ucl_aliases = {
            'psg', 'paris saint-germain', 'paris sg', 'paris',
            'real madrid', 'arsenal', 'man city', 'manchester city',
            'barcelona', 'fc bayern', 'bayern munich', 'bayern munchen',
            'liverpool', 'inter de milan', 'inter', 'inter milan',
            'atletico madrid', 'ath madrid', 'atletico',
            'man united', 'manchester united', 'man. utd',
            'borussia dortmund', 'dortmund',
            'roma', 'as roma',
            'aston villa', 'porto', 'fc porto', 'oporto',
            'sporting', 'sporting cp', 'sporting clube de portugal',
            'psv', 'psv eindhoven', 'real betis', 'betis',
            'club brugge', 'club brugge kv', 'club brujas',
            'rb leipzig', 'leipzig', 'napoli', 'napoles',
            'galatasaray', 'galatasaray sk', 'villarreal', 'villarreal cf',
            'fenerbahce', 'fenerbahce sk', 'lille', 'lille osc',
            'feyenoord', 'feyenoord rotterdam',
            'shakhtar d.', 'shakhtar donetsk', 'fk shakhtar donetsk', 'shakhtar',
            'bodo/glimt', 'fk bodo/glimt', 'bodo glimt',
            'como', 'como 1907', 'stuttgart', 'vfb stuttgart',
            'lens', 'rc lens', 'racing club de lens',
            'slavia prague', 'sk slavia praha', 'slavia',
            'aek athens', 'aek', 'viking fk', 'viking',
            'lask', 'lask linz',
            'slovan bratislava', 'sk slovan bratislava',
            'sabah fk', 'sabah'
        }
        def is_ucl_team(norm_name):
            return norm_name in ucl_aliases
            
        mask = df_csv['Home_norm'].apply(is_ucl_team) & df_csv['Away_norm'].apply(is_ucl_team)
        df_csv = df_csv[mask]
        print(f"Filtrado a {len(df_csv)} partidos de equipos Champions.")

    cursor = db_conn.cursor()
    cursor.execute("SELECT Fecha, Local_ID, Visitante_ID FROM futbol_partidos")
    existing_matches = {(row[0], row[1], row[2]) for row in cursor.fetchall()}
    
    inserted = 0
    for index, row in df_csv.iterrows():
        home_name = row['HomeTeam']
        away_name = row['AwayTeam']
        
        local_id = get_or_create_team(cursor, home_name, league_name)
        visitante_id = get_or_create_team(cursor, away_name, league_name)
        
        fecha = row['Fecha']
        if (fecha, local_id, visitante_id) in existing_matches:
            continue
            
        # Insert match
        cursor.execute('''
            INSERT INTO futbol_partidos (
                Fecha, Temporada, Local_ID, Visitante_ID, Goles_Local, Goles_Visitante,
                Cuota_Local, Cuota_Empate, Cuota_Visitante, MaxCH, MaxCD, MaxCA, AvgCH, AvgCD, AvgCA
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            fecha, '2025', local_id, visitante_id, 
            int(row.get('FTHG', 0)) if pd.notna(row.get('FTHG')) else 0, 
            int(row.get('FTAG', 0)) if pd.notna(row.get('FTAG')) else 0,
            row.get('B365H') if pd.notna(row.get('B365H')) else (row.get('AvgH') if pd.notna(row.get('AvgH')) else None),
            row.get('B365D') if pd.notna(row.get('B365D')) else (row.get('AvgD') if pd.notna(row.get('AvgD')) else None),
            row.get('B365A') if pd.notna(row.get('B365A')) else (row.get('AvgA') if pd.notna(row.get('AvgA')) else None),
            row.get('MaxCH') if pd.notna(row.get('MaxCH')) else None,
            row.get('MaxCD') if pd.notna(row.get('MaxCD')) else None,
            row.get('MaxCA') if pd.notna(row.get('MaxCA')) else None,
            row.get('AvgCH') if pd.notna(row.get('AvgCH')) else None,
            row.get('AvgCD') if pd.notna(row.get('AvgCD')) else None,
            row.get('AvgCA') if pd.notna(row.get('AvgCA')) else None
        ))
        
        partido_id = cursor.lastrowid
        
        # Insert stats for home team
        cursor.execute('''
            INSERT INTO futbol_estadisticas (
                Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            partido_id, local_id, 1,
            int(row['HS']) if 'HS' in row and pd.notna(row['HS']) else 0,
            int(row['HST']) if 'HST' in row and pd.notna(row['HST']) else 0,
            int(row['HF']) if 'HF' in row and pd.notna(row['HF']) else 0,
            int(row['HC']) if 'HC' in row and pd.notna(row['HC']) else 0,
            int(row['HY']) if 'HY' in row and pd.notna(row['HY']) else 0,
            int(row['HR']) if 'HR' in row and pd.notna(row['HR']) else 0
        ))
        
        # Insert stats for away team
        cursor.execute('''
            INSERT INTO futbol_estadisticas (
                Partido_ID, Equipo_ID, Es_Local, Tiros, Tiros_Al_Arco, Faltas, Corners, Tarjetas_Amarillas, Tarjetas_Rojas
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            partido_id, visitante_id, 0,
            int(row['AS']) if 'AS' in row and pd.notna(row['AS']) else 0,
            int(row['AST']) if 'AST' in row and pd.notna(row['AST']) else 0,
            int(row['AF']) if 'AF' in row and pd.notna(row['AF']) else 0,
            int(row['AC']) if 'AC' in row and pd.notna(row['AC']) else 0,
            int(row['AY']) if 'AY' in row and pd.notna(row['AY']) else 0,
            int(row['AR']) if 'AR' in row and pd.notna(row['AR']) else 0
        ))
        
        existing_matches.add((fecha, local_id, visitante_id))
        inserted += 1
        
    db_conn.commit()
    print(f"  -> Insertados {inserted} partidos.")

def main():
    conn = sqlite3.connect('DB-Fut-Beis.db')
    
    # 1. Process Big 5 Leagues (-3m.csv)
    big5_files = {
        'E0-3m.csv': 'Premier League',
        'SP1-3m.csv': 'La Liga',
        'I1-3m.csv': 'Serie A',
        'F1-3m.csv': 'Ligue 1',
        'D1-3m.csv': 'Bundesliga'
    }
    
    for filename, league in big5_files.items():
        filepath = os.path.join('datos_crudos', filename)
        insert_matches_from_csv(filepath, conn, league, is_champ_file=False)
        
    # 2. Get Champions League teams
    ucl_teams_norm = []
    ucl_csv_path = os.path.join('datos_crudos', 'champions26-27.csv')
    if os.path.exists(ucl_csv_path):
        df_ucl = pd.read_csv(ucl_csv_path)
        ucl_teams_norm = [normalize_name(t) for t in df_ucl['Squad'].tolist()]
        print(f"Cargados {len(ucl_teams_norm)} equipos de Champions League.")
    else:
        print(f"Advertencia: no se encontró {ucl_csv_path}")

    # 3. Process -Champ.csv files (Filter for Champions teams, insert as "Champions League")
    champ_files = [f for f in os.listdir('datos_crudos') if f.endswith('-Champ.csv')]
    for filename in champ_files:
        filepath = os.path.join('datos_crudos', filename)
        # Any team created here will be assigned to 'Champions League' if not exists
        insert_matches_from_csv(filepath, conn, 'Champions League', is_champ_file=True, ucl_teams_norm=ucl_teams_norm)
        
    conn.close()
    print("Proceso finalizado.")

if __name__ == '__main__':
    main()
