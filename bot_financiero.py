import requests
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime

def obtener_momios_en_vivo(deporte="baseball_mlb"):
    print(f"Buscando momios en vivo para: {deporte}...")
    
    
    API_KEY = "e5ef8159bd6e67270c9e7de7ce7b8d57"
    
    url = f"https://api.the-odds-api.com/v4/sports/{deporte}/odds/"
    
    parametros = {
        "apiKey": API_KEY,
        "regions": "us",           # 'us' extrae casas como DraftKings, FanDuel, BetMGM
        "markets": "h2h",          # h2h = Head to Head (Ganador del partido / Moneyline)
        "oddsFormat": "decimal"    # Formato decimal (ej. 2.50) para facilitar la matemática
    }

    respuesta = requests.get(url, params=parametros)
    
    if respuesta.status_code != 200:
        print(f" Error al conectar: {respuesta.status_code}")
        return None

    datos = respuesta.json()
    lista_cuotas = []

    # Procesar el JSON gigante para sacar solo lo que nos importa
    for partido in datos:
        equipo_local = partido.get("home_team")
        equipo_visita = partido.get("away_team")
        
        # Tomamos solo la primera casa de apuestas disponible para el ejemplo
        if partido.get("bookmakers"):
            casino = partido["bookmakers"][0]
            nombre_casino = casino["title"]
            
            # Navegar hasta los momios de ganador (h2h)
            for mercado in casino["markets"]:
                if mercado["key"] == "h2h":
                    outcomes = mercado["outcomes"]
                    
                    # Extraer cuotas
                    cuota_local = next((item["price"] for item in outcomes if item["name"] == equipo_local), None)
                    cuota_visita = next((item["price"] for item in outcomes if item["name"] == equipo_visita), None)
                    
                    fila = {
                        "Partido": f"{equipo_local} vs {equipo_visita}",
                        "Local": equipo_local,
                        "Visita": equipo_visita,
                        "Casino": nombre_casino,
                        "Momio_Local": cuota_local,
                        "Momio_Visita": cuota_visita
                    }
                    lista_cuotas.append(fila)

    # Convertir a DataFrame para análisis fácil
    df_momios = pd.DataFrame(lista_cuotas)
    
    if not df_momios.empty:
        # Calcular la Probabilidad Implícita del Casino (1 / Momio)
        df_momios['Prob_Casino_Local'] = (1 / df_momios['Momio_Local']) * 100
        df_momios['Prob_Casino_Visita'] = (1 / df_momios['Momio_Visita']) * 100
        
        # Redondear para que se vea limpio
        df_momios = df_momios.round({'Prob_Casino_Local': 1, 'Prob_Casino_Visita': 1})
        
        print(f" Se encontraron {len(df_momios)} partidos con cuotas abiertas.")
        return df_momios
    else:
        print(" No se encontraron cuotas para este deporte en este momento.")
        return pd.DataFrame()


def analizar_value_bets(df_momios):
    print("Consultando predicciones reales al servidor FastAPI...")
    probabilidades_ia = []
    
    for index, row in df_momios.iterrows():
        local = row['Local']
        visita = row['Visita']
        
        # Hacemos una petición a tu propia API (Asegúrate de que Uvicorn esté corriendo)
        url_api = f"http://localhost:8000/api/pronostico/beisbol?local={local}&visitante={visita}"
        
        try:
            respuesta = requests.get(url_api)
            if respuesta.status_code == 200:
                datos = respuesta.json()
                # Extraemos la probabilidad de victoria del local que calculó tu Random Forest
                prob_local_ia = datos['victoria']['local_pct']
                probabilidades_ia.append(prob_local_ia)
            else:
                print(f" No se pudo obtener pronóstico para {local} vs {visita}")
                probabilidades_ia.append(0.0) # Si falla, ponemos 0 para que no invierta
        except Exception as e:
            print(f" Error de conexión con FastAPI: {e}")
            probabilidades_ia.append(0.0)
            
    # Asignamos las predicciones reales de tu IA al DataFrame
    df_momios['Prob_IA_Local'] = probabilidades_ia
    
    df_momios['Ventaja_Local_%'] = df_momios['Prob_IA_Local'] - df_momios['Prob_Casino_Local']
    
    umbral_seguridad = 4.0 
    oportunidades = df_momios[df_momios['Ventaja_Local_%'] >= umbral_seguridad].copy()
    oportunidades = oportunidades.sort_values(by='Ventaja_Local_%', ascending=False)
    
    print("-" * 60)
    if not oportunidades.empty:
        print(f" ¡Se detectaron {len(oportunidades)} Oportunidades de Inversión!\n")
        columnas_finales = ['Partido', 'Momio_Local', 'Prob_Casino_Local', 'Prob_IA_Local', 'Ventaja_Local_%']
        print(oportunidades[columnas_finales].to_string(index=False))
        return oportunidades
    else:
        print(" El mercado está perfectamente ajustado.")
        return pd.DataFrame()


def registrar_inversiones_simuladas(df_oportunidades):
    if df_oportunidades.empty:
        return
        
    print("\n Registrando compras en el portafolio (SQLite)...")
    
    # 1. Preparar los datos para la base de datos
    df_portafolio = df_oportunidades.copy()
    df_portafolio['Fecha_Compra'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_portafolio['Inversion_Simulada'] = 100.0  # Simulamos apostar $100 MXN/USD a cada oportunidad
    
    # Calcular cuánto ganaríamos si acertamos (Inversión * Momio)
    df_portafolio['Ganancia_Potencial'] = df_portafolio['Inversion_Simulada'] * df_portafolio['Momio_Local']
    df_portafolio['Estado'] = 'Pendiente' # Pendiente hasta que acabe el partido
    
    # Limpiar columnas innecesarias para la DB
    columnas_db = ['Fecha_Compra', 'Partido', 'Local', 'Visita', 'Casino', 
                   'Momio_Local', 'Prob_IA_Local', 'Ventaja_Local_%', 
                   'Inversion_Simulada', 'Ganancia_Potencial', 'Estado']
                   
    df_final = df_portafolio[columnas_db]
    
    # 2. Conectar a SQLite y guardar
    conexion = sqlite3.connect('DB-Fut-Beis.db')
    
    try:
        # if_exists='append' agrega las nuevas inversiones sin borrar las anteriores
        df_final.to_sql('bot_portafolio', conexion, if_exists='append', index=False)
        print(f" ¡{len(df_final)} transacciones registradas exitosamente en la tabla 'bot_portafolio'!")
    except Exception as e:
        print(f" Error al guardar en base de datos: {e}")
    finally:
        conexion.close()


df_mercado = obtener_momios_en_vivo("baseball_mlb")

if df_mercado is not None and not df_mercado.empty:
    df_inversiones = analizar_value_bets(df_mercado)
    
    if not df_inversiones.empty:
        registrar_inversiones_simuladas(df_inversiones)