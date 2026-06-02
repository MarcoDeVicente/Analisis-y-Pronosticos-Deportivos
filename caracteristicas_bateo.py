import sqlite3
import pandas as pd

def calcular_forma_ofensiva(db_path='DB-Fut-Beis.db', ventana_juegos=7):
    print("Extrayendo el historial de resultados para evaluar la Ofensiva...")
    conexion = sqlite3.connect(db_path)
    
    # Extraemos el historial de partidos
    query = '''
        SELECT 
            p.Partido_ID, p.Fecha, 
            eL.Nombre as Local, p.Carreras_Local, 
            eV.Nombre as Visitante, p.Carreras_Visitante
        FROM beisbol_partidos p
        JOIN beisbol_equipos eL ON p.Local_ID = eL.Equipo_ID
        JOIN beisbol_equipos eV ON p.Visitante_ID = eV.Equipo_ID
        ORDER BY p.Fecha ASC
    '''
    df_partidos = pd.read_sql_query(query, conexion)
    conexion.close()

    # Convertimos la fecha a formato cronológico
    df_partidos['Fecha'] = pd.to_datetime(df_partidos['Fecha'])

    # Separamos el rendimiento como Local y como Visitante
    local_stats = df_partidos[['Partido_ID', 'Fecha', 'Local', 'Carreras_Local']].copy()
    local_stats.columns = ['Partido_ID', 'Fecha', 'Equipo', 'Carreras_Anotadas']
    
    visitante_stats = df_partidos[['Partido_ID', 'Fecha', 'Visitante', 'Carreras_Visitante']].copy()
    visitante_stats.columns = ['Partido_ID', 'Fecha', 'Equipo', 'Carreras_Anotadas']

    # Unimos todo para tener la línea de tiempo corrida de cada franquicia
    df_equipos = pd.concat([local_stats, visitante_stats]).sort_values(by=['Equipo', 'Fecha'])

    print(f"Calculando el promedio de carreras en los ultimos {ventana_juegos} juegos...")

    # El shift(1) mágico para no ver el futuro
    df_equipos['Carreras_Prom_Recientes'] = df_equipos.groupby('Equipo')['Carreras_Anotadas'].transform(
        lambda x: x.rolling(window=ventana_juegos, min_periods=1).mean().shift(1)
    )

    df_equipos['Carreras_Prom_Recientes'] = df_equipos['Carreras_Prom_Recientes'].round(2)
    df_equipos = df_equipos.dropna()

    print("\n--- Estado de Forma Reciente: OFENSIVAS ---")
    
    yankees_stats = df_equipos[df_equipos['Equipo'] == 'New York Yankees'].tail(5)
    print(yankees_stats[['Fecha', 'Equipo', 'Carreras_Anotadas', 'Carreras_Prom_Recientes']])
    
    return df_equipos

# Ejecutar el cálculo
df_ofensiva = calcular_forma_ofensiva()