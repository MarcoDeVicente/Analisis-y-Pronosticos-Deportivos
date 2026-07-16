import sqlite3
import pandas as pd
import numpy as np

def weighted_avg(values):
    """ Función para dar peso triple a los últimos 3 partidos """
    if len(values) == 0:
        return 0
    weights = np.ones(len(values))
    for i in range(max(0, len(values)-3), len(values)):
        weights[i] = 3
    return np.average(values, weights=weights)

def calcular_forma_reciente(db_path='DB-Fut-Beis.db', ventana_partidos=10):
    print("Conectando a la base de datos y extrayendo el historial...")
    conexion = sqlite3.connect(db_path)
    
    # 1. Extraemos los partidos y los nombres de los equipos
    query = '''
        SELECT 
            p.Partido_ID, p.Fecha, 
            eL.Nombre as Local, p.Goles_Local, 
            eV.Nombre as Visitante, p.Goles_Visitante
        FROM futbol_partidos p
        JOIN futbol_equipos eL ON p.Local_ID = eL.Equipo_ID
        JOIN futbol_equipos eV ON p.Visitante_ID = eV.Equipo_ID
        ORDER BY p.Fecha ASC
    '''
    df_partidos = pd.read_sql_query(query, conexion)
    conexion.close()

    # 1.5 Cargar Rankings FIFA para Multiplicador de Rival
    try:
        df_ranking = pd.read_csv('FIFA_Ranking_WC2026.csv')
        mappings = {
            "Bosnia and Herzegovina": "Bosnia & Herzegovina",
            "Curaçao": "Curacao",
            "Ivory coast": "Ivory Coast",
            "IR Iran": "Iran"
        }
        df_ranking['Team'] = df_ranking['Team'].replace(mappings)
        df_ranking['Multiplicador_Rival'] = df_ranking['FIFA_Points'] / 1500.0
    except Exception as e:
        print(f"Advertencia: No se pudo cargar ranking. {e}")
        df_ranking = pd.DataFrame(columns=['Team', 'Multiplicador_Rival'])

    # 2. Transformación: De "Partido" a "Rendimiento por Equipo"
    local_stats = df_partidos[['Partido_ID', 'Fecha', 'Local', 'Goles_Local', 'Goles_Visitante', 'Visitante']].copy()
    local_stats.columns = ['Partido_ID', 'Fecha', 'Equipo', 'Goles_A Favor', 'Goles_En_Contra', 'Rival']
    
    visitante_stats = df_partidos[['Partido_ID', 'Fecha', 'Visitante', 'Goles_Visitante', 'Goles_Local', 'Local']].copy()
    visitante_stats.columns = ['Partido_ID', 'Fecha', 'Equipo', 'Goles_A Favor', 'Goles_En_Contra', 'Rival']

    # Unimos todo en un solo DataFrame gigante ordenado por fecha
    df_equipos = pd.concat([local_stats, visitante_stats]).sort_values(by=['Equipo', 'Fecha'])

    df_equipos = df_equipos.merge(df_ranking[['Team', 'Multiplicador_Rival']], left_on='Rival', right_on='Team', how='left')
    df_equipos['Multiplicador_Rival'] = df_equipos['Multiplicador_Rival'].fillna(1.0)
    
    df_equipos['GF_Ponderado'] = df_equipos['Goles_A Favor'] * df_equipos['Multiplicador_Rival']
    df_equipos['GC_Ponderado'] = df_equipos['Goles_En_Contra'] / df_equipos['Multiplicador_Rival']

    # 3. El Motor Matemático (Evitando la Fuga de Datos)
    print(f"Calculando promedios moviles PONDERADOS de los ultimos {ventana_partidos} partidos...")
    
    # Agrupamos por equipo y calculamos el promedio móvil (rolling)
    df_equipos['Promedio_GF'] = df_equipos.groupby('Equipo')['GF_Ponderado'].transform(
        lambda x: x.rolling(window=ventana_partidos, min_periods=1).apply(weighted_avg, raw=True).shift(1)
    )
    
    df_equipos['Promedio_GC'] = df_equipos.groupby('Equipo')['GC_Ponderado'].transform(
        lambda x: x.rolling(window=ventana_partidos, min_periods=1).apply(weighted_avg, raw=True).shift(1)
    )

    # 4. Mostrar Resultados (Ejemplo con Sudafrica y Canada)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print("\n--- Estado de Forma Reciente: South Africa ---")
    sa_stats = df_equipos[df_equipos['Equipo'] == 'South Africa'].tail(6)
    print(sa_stats[['Fecha', 'Equipo', 'Rival', 'Goles_A Favor', 'GF_Ponderado', 'Promedio_GF', 'Promedio_GC']])

    print("\n--- Estado de Forma Reciente: Canada ---")
    can_stats = df_equipos[df_equipos['Equipo'] == 'Canada'].tail(6)
    print(can_stats[['Fecha', 'Equipo', 'Rival', 'Goles_A Favor', 'GF_Ponderado', 'Promedio_GF', 'Promedio_GC']])

    # ---------------------------------------------------------
    # FASE 5: CONSTRUCCIÓN DE LA MATRIZ DE ENTRENAMIENTO
    # ---------------------------------------------------------
    print("\nEnsamblando la Matriz de Entrenamiento para el modelo...")

    # Volvemos a traer los datos originales del partido (para saber quién fue local/visita)
    conexion = sqlite3.connect(db_path)
    df_base = pd.read_sql_query('''
        SELECT p.Partido_ID, eL.Nombre as Local, eV.Nombre as Visitante, p.Goles_Local, p.Goles_Visitante
        FROM futbol_partidos p
        JOIN futbol_equipos eL ON p.Local_ID = eL.Equipo_ID
        JOIN futbol_equipos eV ON p.Visitante_ID = eV.Equipo_ID
    ''', conexion)
    conexion.close()

    # Separamos las estadísticas calculadas para Locales y Visitantes
    stats_como_local = df_equipos[['Partido_ID', 'Equipo', 'Promedio_GF', 'Promedio_GC']].rename(
        columns={'Equipo': 'Local', 'Promedio_GF': 'Local_GF_Prom', 'Promedio_GC': 'Local_GC_Prom'}
    )
    
    stats_como_visita = df_equipos[['Partido_ID', 'Equipo', 'Promedio_GF', 'Promedio_GC']].rename(
        columns={'Equipo': 'Visitante', 'Promedio_GF': 'Visita_GF_Prom', 'Promedio_GC': 'Visita_GC_Prom'}
    )

    # Unimos todo usando el Partido_ID como puente
    dataset_final = df_base.merge(stats_como_local, on=['Partido_ID', 'Local'], how='inner')
    dataset_final = dataset_final.merge(stats_como_visita, on=['Partido_ID', 'Visitante'], how='inner')

    # Eliminamos las filas que tengan NaN (los primeros 5 partidos de cada equipo no tienen promedio previo)
    dataset_final = dataset_final.dropna()

    # LA VARIABLE OBJETIVO (Target): 1 = Gana Local, 0 = Empate, 2 = Gana Visitante
    def determinar_ganador(row):
        if row['Goles_Local'] > row['Goles_Visitante']: return 1
        elif row['Goles_Local'] < row['Goles_Visitante']: return 2
        else: return 0
        
    dataset_final['Target_Ganador'] = dataset_final.apply(determinar_ganador, axis=1)

    print(f"\nDataset listo! Total de partidos procesables para Machine Learning: {len(dataset_final)}")
    
    # Mostrar una muestra de cómo lo verá el modelo
    columnas_modelo = ['Local', 'Visitante', 'Local_GF_Prom', 'Local_GC_Prom', 'Visita_GF_Prom', 'Visita_GC_Prom', 'Target_Ganador']
    print("\nVisualizacion de la Matriz Final (Primeros 5 partidos):")
    print(dataset_final[columnas_modelo].head())

    # Opcional: Guardarlo en un CSV limpio para dárselo a Scikit-Learn
    dataset_final.to_csv('Dataset_Futbol_ML.csv', index=False)
    
    return df_equipos

# Ejecutar el cálculo
df_features = calcular_forma_reciente() 