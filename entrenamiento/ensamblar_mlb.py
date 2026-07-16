import sqlite3
import pandas as pd
from caracteristicas_Beisbol import calcular_forma_pitchers
from caracteristicas_bateo import calcular_forma_ofensiva

def construir_dataset_mlb(db_path='DB-Fut-Beis.db'):
    print("Calculando metricas de Pitchers y Ofensivas...")
    # 1. Obtenemos las características crudas
    df_pitchers = calcular_forma_pitchers(db_path)
    df_ofensivas = calcular_forma_ofensiva(db_path)

    # 2. Obtenemos la base de los partidos reales
    conexion = sqlite3.connect(db_path)
    df_base = pd.read_sql_query('''
        SELECT p.Partido_ID, eL.Nombre as Local, eV.Nombre as Visitante, p.Carreras_Local, p.Carreras_Visitante
        FROM beisbol_partidos p
        JOIN beisbol_equipos eL ON p.Local_ID = eL.Equipo_ID
        JOIN beisbol_equipos eV ON p.Visitante_ID = eV.Equipo_ID
    ''', conexion)
    conexion.close()

    print("\nCruzando datos para armar la Matriz de Entrenamiento...")

    # --- 3. SEPARAMOS DATOS DE LOCALES Y VISITANTES ---
    
    # A) Pitchers
    pitchers_local = df_pitchers[['Partido_ID', 'ERA_Reciente', 'Ponches_Prom_Reciente']].rename(
        columns={'ERA_Reciente': 'Local_Pitcher_ERA', 'Ponches_Prom_Reciente': 'Local_Pitcher_K'}
    )
    # Como la tabla de pitchers tiene una fila por lanzador, filtramos duplicados por si un relevista se coló
    pitchers_local = pitchers_local.drop_duplicates(subset=['Partido_ID'], keep='first')

    pitchers_visita = df_pitchers[['Partido_ID', 'ERA_Reciente', 'Ponches_Prom_Reciente']].rename(
        columns={'ERA_Reciente': 'Visita_Pitcher_ERA', 'Ponches_Prom_Reciente': 'Visita_Pitcher_K'}
    )
    pitchers_visita = pitchers_visita.drop_duplicates(subset=['Partido_ID'], keep='last')

    # B) Ofensivas (Usando el Equipo para saber si era Local o Visita)
    ofensiva_local = df_ofensivas[['Partido_ID', 'Equipo', 'Carreras_Prom_Recientes']].rename(
        columns={'Equipo': 'Local', 'Carreras_Prom_Recientes': 'Local_Bateo_Prom'}
    )
    ofensiva_visita = df_ofensivas[['Partido_ID', 'Equipo', 'Carreras_Prom_Recientes']].rename(
        columns={'Equipo': 'Visitante', 'Carreras_Prom_Recientes': 'Visita_Bateo_Prom'}
    )

    # --- 4. ENSAMBLAJE FINAL (MERGE) ---
    dataset = df_base.merge(ofensiva_local, on=['Partido_ID', 'Local'], how='inner')
    dataset = dataset.merge(ofensiva_visita, on=['Partido_ID', 'Visitante'], how='inner')
    dataset = dataset.merge(pitchers_local, on='Partido_ID', how='inner')
    dataset = dataset.merge(pitchers_visita, on='Partido_ID', how='inner')

    # Eliminamos nulos (los primeros juegos de la temporada que no tienen historial)
    dataset = dataset.dropna()

    # --- 5. LA VARIABLE OBJETIVO (TARGET) ---
    # 1 = Gana Local, 0 = Gana Visitante
    dataset['Target_Ganador'] = (dataset['Carreras_Local'] > dataset['Carreras_Visitante']).astype(int)

    print(f"\nDataset de Beisbol listo! Total de partidos procesables: {len(dataset)}")
    
    # Ordenamos las columnas para que se vea limpio
    columnas_finales = [
        'Local', 'Visitante', 
        'Local_Pitcher_ERA', 'Local_Pitcher_K', 'Local_Bateo_Prom',
        'Visita_Pitcher_ERA', 'Visita_Pitcher_K', 'Visita_Bateo_Prom', 
        'Target_Ganador'
    ]
    
    print("\nMuestra de la Matriz Final (Primeras 5 filas):")
    print(dataset[columnas_finales].head())

    # Lo guardamos en CSV para que el Random Forest lo pueda leer
    dataset.to_csv('Dataset_Beisbol_ML.csv', index=False)
    
    return dataset

# Ejecutamos el ensamblador
dataset_final_mlb = construir_dataset_mlb()