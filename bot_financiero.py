import requests
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime
import os

def inicializar_db_schema_y_semilla():
    DB_PATH = 'DB-Fut-Beis.db'
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    
    tabla_actualizada = False
    try:
        cursor.execute("PRAGMA table_info(bot_portafolio)")
        columns = [row[1] for row in cursor.fetchall()]
        if columns and "Apuesta_A" in columns:
            tabla_actualizada = True
    except Exception:
        pass
        
    if not tabla_actualizada:
        print(" Actualizando el esquema de la tabla 'bot_portafolio'...")
        cursor.execute("DROP TABLE IF EXISTS bot_portafolio")
        
        cursor.execute("""
            CREATE TABLE bot_portafolio (
                Fecha_Compra TEXT,
                Partido TEXT,
                Local TEXT,
                Visita TEXT,
                Casino TEXT,
                Momio_Local REAL,
                Momio_Visita REAL,
                Prob_Casino_Local REAL,
                Prob_Casino_Visita REAL,
                Prob_IA_Local REAL,
                Prob_IA_Visita REAL,
                Apuesta_A TEXT,
                Momio_Apostado REAL,
                Prob_IA_Apostado REAL,
                "Ventaja_%" REAL,
                Inversion_Simulada REAL,
                Ganancia_Potencial REAL,
                Estado TEXT
            )
        """)
        conexion.commit()
        print(" ¡Tabla 'bot_portafolio' inicializada exitosamente (vacía)!")
        
    conexion.close()

def obtener_momios_en_vivo(deporte="baseball_mlb"):
    print(f"Buscando momios en vivo para: {deporte}...")
    
    API_KEY = "e5ef8159bd6e67270c9e7de7ce7b8d57"
    url = f"https://api.the-odds-api.com/v4/sports/{deporte}/odds/"
    
    parametros = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "decimal"
    }

    try:
        respuesta = requests.get(url, params=parametros)
        if respuesta.status_code != 200:
            print(f" Error al conectar: {respuesta.status_code}")
            return None
        datos = respuesta.json()
    except Exception as e:
        print(f" Error de conexión con The Odds API: {e}")
        return None

    lista_cuotas = []

    for partido in datos:
        equipo_local = partido.get("home_team")
        equipo_visita = partido.get("away_team")
        
        if partido.get("bookmakers"):
            casino = partido["bookmakers"][0]
            nombre_casino = casino["title"]
            
            for mercado in casino["markets"]:
                if mercado["key"] == "h2h":
                    outcomes = mercado["outcomes"]
                    
                    cuota_local = next((item["price"] for item in outcomes if item["name"] == equipo_local), None)
                    cuota_visita = next((item["price"] for item in outcomes if item["name"] == equipo_visita), None)
                    
                    if cuota_local is not None and cuota_visita is not None:
                        fila = {
                            "Partido": f"{equipo_local} vs {equipo_visita}",
                            "Local": equipo_local,
                            "Visita": equipo_visita,
                            "Casino": nombre_casino,
                            "Momio_Local": cuota_local,
                            "Momio_Visita": cuota_visita
                        }
                        lista_cuotas.append(fila)

    df_momios = pd.DataFrame(lista_cuotas)
    
    if not df_momios.empty:
        # Calcular la Probabilidad Implícita del Casino (1 / Momio)
        df_momios['Prob_Casino_Local'] = (1 / df_momios['Momio_Local']) * 100
        df_momios['Prob_Casino_Visita'] = (1 / df_momios['Momio_Visita']) * 100
        
        df_momios = df_momios.round({'Prob_Casino_Local': 1, 'Prob_Casino_Visita': 1})
        print(f" Se encontraron {len(df_momios)} partidos con cuotas abiertas.")
        return df_momios
    else:
        print(" No se encontraron cuotas para este deporte en este momento.")
        return pd.DataFrame()

def analizar_value_bets(df_momios):
    if df_momios.empty:
        return pd.DataFrame()
        
    print("Consultando predicciones reales al servidor FastAPI...")
    lista_oportunidades = []
    umbral_seguridad = 4.0 
    
    for index, row in df_momios.iterrows():
        local = row['Local']
        visita = row['Visita']
        momio_local = row['Momio_Local']
        momio_visita = row['Momio_Visita']
        
        url_api = f"http://localhost:8000/api/pronostico/beisbol?local={local}&visitante={visita}"
        
        try:
            respuesta = requests.get(url_api)
            if respuesta.status_code == 200:
                datos = respuesta.json()
                prob_local_ia = datos['victoria']['local_pct']
                prob_visita_ia = datos['victoria']['visita_pct']
            else:
                print(f" No se pudo obtener pronóstico para {local} vs {visita}")
                continue
        except Exception as e:
            print(f" Error de conexión con FastAPI para {local} vs {visita}: {e}")
            continue
            
        prob_casino_local = (1 / momio_local) * 100
        prob_casino_visita = (1 / momio_visita) * 100
        
        ventaja_local = prob_local_ia - prob_casino_local
        ventaja_visita = prob_visita_ia - prob_casino_visita
        
        # Evaluar apuesta de valor en Local
        if ventaja_local >= umbral_seguridad:
            fila = {
                "Partido": row["Partido"],
                "Local": local,
                "Visita": visita,
                "Casino": row["Casino"],
                "Momio_Local": momio_local,
                "Momio_Visita": momio_visita,
                "Prob_Casino_Local": round(prob_casino_local, 1),
                "Prob_Casino_Visita": round(prob_casino_visita, 1),
                "Prob_IA_Local": prob_local_ia,
                "Prob_IA_Visita": prob_visita_ia,
                "Apuesta_A": "Local",
                "Momio_Apostado": momio_local,
                "Prob_IA_Apostado": prob_local_ia,
                "Ventaja_%": round(ventaja_local, 1)
            }
            lista_oportunidades.append(fila)
            
        # Evaluar apuesta de valor en Visita
        if ventaja_visita >= umbral_seguridad:
            fila = {
                "Partido": row["Partido"],
                "Local": local,
                "Visita": visita,
                "Casino": row["Casino"],
                "Momio_Local": momio_local,
                "Momio_Visita": momio_visita,
                "Prob_Casino_Local": round(prob_casino_local, 1),
                "Prob_Casino_Visita": round(prob_casino_visita, 1),
                "Prob_IA_Local": prob_local_ia,
                "Prob_IA_Visita": prob_visita_ia,
                "Apuesta_A": "Visita",
                "Momio_Apostado": momio_visita,
                "Prob_IA_Apostado": prob_visita_ia,
                "Ventaja_%": round(ventaja_visita, 1)
            }
            lista_oportunidades.append(fila)
            
    df_oportunidades = pd.DataFrame(lista_oportunidades)
    
    print("-" * 60)
    if not df_oportunidades.empty:
        df_oportunidades = df_oportunidades.sort_values(by='Ventaja_%', ascending=False)
        print(f" ¡Se detectaron {len(df_oportunidades)} Oportunidades de Inversión!\n")
        columnas_finales = ['Partido', 'Apuesta_A', 'Momio_Apostado', 'Prob_IA_Apostado', 'Ventaja_%']
        print(df_oportunidades[columnas_finales].to_string(index=False))
        return df_oportunidades
    else:
        print(" El mercado está perfectamente ajustado.")
        return pd.DataFrame()

def registrar_inversiones_simuladas(df_oportunidades):
    if df_oportunidades.empty:
        return
        
    inicializar_db_schema_y_semilla()
        
    print("\n Registrando compras en el portafolio (SQLite)...")
    
    df_portafolio = df_oportunidades.copy()
    df_portafolio['Fecha_Compra'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_portafolio['Inversion_Simulada'] = 100.0  
    
    df_portafolio['Ganancia_Potencial'] = df_portafolio['Inversion_Simulada'] * df_portafolio['Momio_Apostado']
    df_portafolio['Estado'] = 'Pendiente' 
    
    columnas_db = ['Fecha_Compra', 'Partido', 'Local', 'Visita', 'Casino', 
                   'Momio_Local', 'Momio_Visita', 'Prob_Casino_Local', 'Prob_Casino_Visita',
                   'Prob_IA_Local', 'Prob_IA_Visita', 'Apuesta_A', 'Momio_Apostado', 
                   'Prob_IA_Apostado', 'Ventaja_%', 'Inversion_Simulada', 
                   'Ganancia_Potencial', 'Estado']
                   
    df_final = df_portafolio[columnas_db]
    
    conexion = sqlite3.connect('DB-Fut-Beis.db')
    
    try:
        df_final.to_sql('bot_portafolio', conexion, if_exists='append', index=False)
        print(f" ¡{len(df_final)} transacciones registradas exitosamente en la tabla 'bot_portafolio'!")
    except Exception as e:
        print(f" Error al guardar en base de datos: {e}")
    finally:
        conexion.close()

if __name__ == "__main__":
    inicializar_db_schema_y_semilla()
    df_mercado = obtener_momios_en_vivo("baseball_mlb")
    if df_mercado is not None and not df_mercado.empty:
        df_inversiones = analizar_value_bets(df_mercado)
        if not df_inversiones.empty:
            registrar_inversiones_simuladas(df_inversiones)