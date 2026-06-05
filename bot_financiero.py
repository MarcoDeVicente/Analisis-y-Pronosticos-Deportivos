import requests
import pandas as pd
import sqlite3
from datetime import datetime

def inicializar_db_schema_y_semilla():
    DB_PATH = 'DB-Fut-Beis.db'
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    
    # Forzamos la actualización de la tabla para incluir los nuevos mercados de Totales
    print(" Verificando y actualizando el esquema de la tabla 'bot_portafolio'...")
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
            Linea_OverUnder REAL,
            Momio_Over REAL,
            Momio_Under REAL,
            Prob_Casino_Local REAL,
            Prob_Casino_Visita REAL,
            Prob_Casino_Over REAL,
            Prob_Casino_Under REAL,
            Prob_IA_Local REAL,
            Prob_IA_Visita REAL,
            Prob_IA_Over REAL,
            Prob_IA_Under REAL,
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
    print("Tabla 'bot_portafolio' inicializada con soporte para Multi-Mercado!")
    conexion.close()

def obtener_momios_en_vivo(deporte="baseball_mlb"):
    print(f"\nBuscando Ganador y Altas/Bajas para: {deporte}...")
    
    API_KEY = "e5ef8159bd6e67270c9e7de7ce7b8d57"
    url = f"https://api.the-odds-api.com/v4/sports/{deporte}/odds/"
    
    # Solicitamos dos mercados al mismo tiempo
    parametros = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h,totals",
        "oddsFormat": "decimal"
    }

    try:
        respuesta = requests.get(url, params=parametros)
        if respuesta.status_code != 200:
            print(f"Error al conectar: {respuesta.status_code}")
            return pd.DataFrame()
        datos = respuesta.json()
    except Exception as e:
        print(f" de conexión con The Odds API: {e}")
        return pd.DataFrame()

    lista_cuotas = []

    for partido in datos:
        equipo_local = partido.get("home_team")
        equipo_visita = partido.get("away_team")
        
        if partido.get("bookmakers"):
            casino = partido["bookmakers"][0]
            nombre_casino = casino["title"]
            
            cuota_local, cuota_visita = None, None
            linea_puntos, cuota_over, cuota_under = None, None, None
            
            # Buscamos en los mercados disponibles
            for mercado in casino["markets"]:
                if mercado["key"] == "h2h":
                    outcomes = mercado["outcomes"]
                    cuota_local = next((item["price"] for item in outcomes if item["name"] == equipo_local), None)
                    cuota_visita = next((item["price"] for item in outcomes if item["name"] == equipo_visita), None)
                
                elif mercado["key"] == "totals":
                    outcomes = mercado["outcomes"]
                    for item in outcomes:
                        if item["name"] == "Over":
                            cuota_over = item["price"]
                            linea_puntos = item["point"]
                        elif item["name"] == "Under":
                            cuota_under = item["price"]
            
            # Si al menos tenemos las cuotas de ganador, guardamos el partido
            if cuota_local and cuota_visita:
                fila = {
                    "Partido": f"{equipo_local} vs {equipo_visita}",
                    "Local": equipo_local,
                    "Visita": equipo_visita,
                    "Casino": nombre_casino,
                    "Momio_Local": cuota_local,
                    "Momio_Visita": cuota_visita,
                    "Linea_OverUnder": linea_puntos,
                    "Momio_Over": cuota_over,
                    "Momio_Under": cuota_under
                }
                lista_cuotas.append(fila)

    df_momios = pd.DataFrame(lista_cuotas)
    
    if not df_momios.empty:
        # Cálculos de Probabilidad Implícita del Casino
        df_momios['Prob_Casino_Local'] = ((1 / df_momios['Momio_Local']) * 100).round(1)
        df_momios['Prob_Casino_Visita'] = ((1 / df_momios['Momio_Visita']) * 100).round(1)
        
        # Probabilidades de Totales (Si el casino las ofreció)
        df_momios['Prob_Casino_Over'] = df_momios['Momio_Over'].apply(lambda x: round((1/x)*100, 1) if pd.notnull(x) else None)
        df_momios['Prob_Casino_Under'] = df_momios['Momio_Under'].apply(lambda x: round((1/x)*100, 1) if pd.notnull(x) else None)
        
        print(f"Se encontraron {len(df_momios)} partidos con cuotas abiertas.")
        return df_momios
    else:
        print("No se encontraron cuotas.")
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
        
        url_api = f"http://localhost:8000/api/pronostico/beisbol?local={local}&visitante={visita}"
        
        try:
            respuesta = requests.get(url_api)
            if respuesta.status_code == 200:
                datos = respuesta.json()
                
                # Extraer IA para Ganador (H2H)
                prob_local_ia = datos['victoria']['local_pct']
                prob_visita_ia = datos['victoria']['visita_pct']
                
                # --- NUEVA LÓGICA PARA TOTALES (OVER/UNDER) ---
                prob_over_ia = None
                prob_under_ia = None
                
                linea_casino = row['Linea_OverUnder']
                
                if pd.notnull(linea_casino):
                    # Convertimos el número 7.5 a la cadena "7_5" para que coincida con tu JSON
                    str_linea = str(linea_casino).replace('.', '_')
                    llave_over = f"over_{str_linea}"
                    llave_under = f"under_{str_linea}"
                    
                    # Buscamos en el diccionario 'mercados'
                    mercados = datos.get('mercados', {})
                    prob_over_ia = mercados.get(llave_over, None)
                    prob_under_ia = mercados.get(llave_under, None)
                
            else:
                continue
        except Exception:
            continue
            
        # 1. Análisis de Ganador (H2H)
        prob_casino_local = row['Prob_Casino_Local']
        prob_casino_visita = row['Prob_Casino_Visita']
        
        ventaja_local = prob_local_ia - prob_casino_local
        ventaja_visita = prob_visita_ia - prob_casino_visita
        
        # Plantilla base para la oportunidad
        base_fila = row.to_dict()
        base_fila.update({
            "Prob_IA_Local": prob_local_ia,
            "Prob_IA_Visita": prob_visita_ia,
            "Prob_IA_Over": prob_over_ia,
            "Prob_IA_Under": prob_under_ia
        })
        
        if ventaja_local >= umbral_seguridad:
            fila_local = base_fila.copy()
            fila_local.update({"Apuesta_A": "Local", "Momio_Apostado": row['Momio_Local'], "Prob_IA_Apostado": prob_local_ia, "Ventaja_%": round(ventaja_local, 1)})
            lista_oportunidades.append(fila_local)
            
        if ventaja_visita >= umbral_seguridad:
            fila_visita = base_fila.copy()
            fila_visita.update({"Apuesta_A": "Visita", "Momio_Apostado": row['Momio_Visita'], "Prob_IA_Apostado": prob_visita_ia, "Ventaja_%": round(ventaja_visita, 1)})
            lista_oportunidades.append(fila_visita)
            
        # 2. Análisis de Altas/Bajas (Si existen datos del casino y de tu IA)
        if pd.notnull(row['Prob_Casino_Over']) and prob_over_ia is not None:
            ventaja_over = prob_over_ia - row['Prob_Casino_Over']
            ventaja_under = prob_under_ia - row['Prob_Casino_Under']
            
            if ventaja_over >= umbral_seguridad:
                fila_over = base_fila.copy()
                fila_over.update({"Apuesta_A": f"Over {row['Linea_OverUnder']}", "Momio_Apostado": row['Momio_Over'], "Prob_IA_Apostado": prob_over_ia, "Ventaja_%": round(ventaja_over, 1)})
                lista_oportunidades.append(fila_over)
                
            if ventaja_under >= umbral_seguridad:
                fila_under = base_fila.copy()
                fila_under.update({"Apuesta_A": f"Under {row['Linea_OverUnder']}", "Momio_Apostado": row['Momio_Under'], "Prob_IA_Apostado": prob_under_ia, "Ventaja_%": round(ventaja_under, 1)})
                lista_oportunidades.append(fila_under)
            
    df_oportunidades = pd.DataFrame(lista_oportunidades)
    
    print("-" * 60)
    if not df_oportunidades.empty:
        df_oportunidades = df_oportunidades.sort_values(by='Ventaja_%', ascending=False)
        print(f"Se detectaron {len(df_oportunidades)} Oportunidades de Inversión!\n")
        columnas_finales = ['Partido', 'Apuesta_A', 'Momio_Apostado', 'Prob_IA_Apostado', 'Ventaja_%']
        print(df_oportunidades[columnas_finales].to_string(index=False))
        return df_oportunidades
    else:
        print(" El mercado está perfectamente ajustado.")
        return pd.DataFrame()

def registrar_inversiones_simuladas(df_oportunidades):
    if df_oportunidades.empty:
        return
        
    print("\nRegistrando compras en el portafolio (SQLite)...")
    
    df_portafolio = df_oportunidades.copy()
    df_portafolio['Fecha_Compra'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_portafolio['Inversion_Simulada'] = 100.0  
    
    df_portafolio['Ganancia_Potencial'] = df_portafolio['Inversion_Simulada'] * df_portafolio['Momio_Apostado']
    df_portafolio['Estado'] = 'Pendiente' 
    
    conexion = sqlite3.connect('DB-Fut-Beis.db')
    try:
        df_portafolio.to_sql('bot_portafolio', conexion, if_exists='append', index=False)
        print(f"{len(df_portafolio)} transacciones registradas exitosamente en la tabla 'bot_portafolio'!")
    except Exception as e:
        print(f"Error al guardar en base de datos: {e}")
    finally:
        conexion.close()

if __name__ == "__main__":
    # 1. Preparamos DB
    inicializar_db_schema_y_semilla()
    # 2. Extraemos todos los mercados
    df_mercado = obtener_momios_en_vivo("baseball_mlb")
    # 3. Analizamos y guardamos
    if df_mercado is not None and not df_mercado.empty:
        df_inversiones = analizar_value_bets(df_mercado)
        if not df_inversiones.empty:
            registrar_inversiones_simuladas(df_inversiones)