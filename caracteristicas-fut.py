import sqlite3
import pandas as pd

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

    # 2. Transformación: De "Partido" a "Rendimiento por Equipo"
    local_stats = df_partidos[['Partido_ID', 'Fecha', 'Local', 'Goles_Local', 'Goles_Visitante']].copy()
    local_stats.columns = ['Partido_ID', 'Fecha', 'Equipo', 'Goles_A Favor', 'Goles_En_Contra']
    
    visitante_stats = df_partidos[['Partido_ID', 'Fecha', 'Visitante', 'Goles_Visitante', 'Goles_Local']].copy()
    visitante_stats.columns = ['Partido_ID', 'Fecha', 'Equipo', 'Goles_A Favor', 'Goles_En_Contra']

    # Unimos todo en un solo DataFrame gigante ordenado por fecha
    df_equipos = pd.concat([local_stats, visitante_stats]).sort_values(by=['Equipo', 'Fecha'])

    # 3. El Motor Matemático (Evitando la Fuga de Datos)
    print(f"Calculando promedios moviles de los ultimos {ventana_partidos} partidos...")
    
    # Agrupamos por equipo y calculamos el promedio móvil (rolling)
    df_equipos['Promedio_GF'] = df_equipos.groupby('Equipo')['Goles_A Favor'].transform(
        lambda x: x.rolling(window=ventana_partidos, min_periods=1).mean().shift(1)
    )
    
    df_equipos['Promedio_GC'] = df_equipos.groupby('Equipo')['Goles_En_Contra'].transform(
        lambda x: x.rolling(window=ventana_partidos, min_periods=1).mean().shift(1)
    )

    # 4. Mostrar Resultados (Ejemplo con México)
    print("\n--- Estado de Forma Reciente: Arsenal ---")
    arsenal_stats = df_equipos[df_equipos['Equipo'] == 'Arsenal'].tail(6)
    print(arsenal_stats[['Fecha', 'Equipo', 'Goles_A Favor', 'Promedio_GF', 'Promedio_GC']])

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