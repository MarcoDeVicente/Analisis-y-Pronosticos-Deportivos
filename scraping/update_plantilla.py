import sqlite3
import requests
import time

# --- CONFIGURACIÓN DE API ---
API_KEY = "089c43a367c9d806cbb3a278e2461925" 
HEADERS = {
    "x-apisports-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

# --- VARIABLES ---
EQUIPOS_MUNDIAL_IDS = [1,2,3,5,6,7,8,9,10,11,12,13,15,16,17,19,20,22,23,25,26,27,28,31,32,19128,1501,1567,1090,1532,1569,5529,770,1531,1113,1108,2386,2384,777,2380,2382,5530,1118,4673,775,1548,1508,1568,1504]
LIGAS_CLASIFICATORIAS = [30, 31, 32, 33, 34, 35, 36] 
TEMPORADAS_ACTIVAS = [2023, 2024, 2025] 

# --- FUNCIONES DE EXTRACCIÓN ---
def procesar_plantilla(equipo_id):
    """Busca al equipo en las distintas eliminatorias continentales."""
    for liga in LIGAS_CLASIFICATORIAS:
        for temporada in TEMPORADAS_ACTIVAS:
            url = f"https://v3.football.api-sports.io/players?team={equipo_id}&league={liga}&season={temporada}"
            
            try:
                respuesta = requests.get(url, headers=HEADERS)
                if respuesta.status_code == 200:
                    datos = respuesta.json()
                    
                    # Si la API arroja un error interno (ej. límite de peticiones)
                    if datos.get('errors'):
                        print(f"   [!] Error API para ID {equipo_id}: {datos['errors']}")
                        # Rompemos para no gastar más llamadas inútiles
                        return None 
                    
                    if datos.get('response'):
                        print(f"   [+] Datos encontrados en Liga {liga} (Temp {temporada})")
                        return calcular_promedios(datos['response'], equipo_id)
                        
            except Exception as e:
                print(f"   [!] Error HTTP en liga {liga}: {e}")
                
            # Pausa para no saturar el servidor
            time.sleep(1)
            
    print(f"   [-] No se encontraron datos para el equipo ID: {equipo_id}")
    return None

def calcular_promedios(jugadores, equipo_id):
    """Calcula la matemática de la plantilla."""
    total_rating = 0.0
    conteo_rating = 0
    total_precision_pases = 0.0
    conteo_pases = 0
    lesiones_activas = 0
    nombre_equipo = ""
    
    for item in jugadores:
        jugador = item['player']
        estadisticas = item['statistics'][0]
        
        if not nombre_equipo:
            nombre_equipo = estadisticas['team']['name']
            
        if jugador.get('injured') == True:
            lesiones_activas += 1
            
        rating = estadisticas['games'].get('rating')
        if rating is not None:
            total_rating += float(rating)
            conteo_rating += 1
            
        pases_acc = estadisticas['passes'].get('accuracy')
        if pases_acc is not None:
            total_precision_pases += float(pases_acc)
            conteo_pases += 1
            
    rating_promedio = round(total_rating / conteo_rating, 2) if conteo_rating > 0 else 6.5
    precision_promedio = round(total_precision_pases / conteo_pases, 2) if conteo_pases > 0 else 75.0
    
    return {
        "equipo_id": equipo_id,
        "nombre": nombre_equipo,
        "rating": rating_promedio,
        "lesiones": lesiones_activas,
        "pases": precision_promedio
    }

# --- FUNCIÓN PRINCIPAL (ENTRY POINT) ---
def actualizar_base_datos():
    print("Iniciando escaneo de plantillas en Eliminatorias...")
    
    conexion = sqlite3.connect("DB-Fut-Beis.db")
    cursor = conexion.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS futbol_estadisticas_plantilla (
            Equipo_ID INTEGER PRIMARY KEY,
            Nombre_Equipo TEXT,
            Rating_Promedio REAL,
            Lesiones_Clave INTEGER,
            Precision_Pases REAL,
            Ultima_Actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    for equipo_id in EQUIPOS_MUNDIAL_IDS:
        print(f"Procesando equipo ID: {equipo_id}...")
        datos = procesar_plantilla(equipo_id)
        
        if datos:
            cursor.execute("""
                INSERT OR REPLACE INTO futbol_estadisticas_plantilla 
                (Equipo_ID, Nombre_Equipo, Rating_Promedio, Lesiones_Clave, Precision_Pases, Ultima_Actualizacion)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (datos['equipo_id'], datos['nombre'], datos['rating'], datos['lesiones'], datos['pases']))
            
            conexion.commit()
            print(f"Guardado: {datos['nombre']} | Rating: {datos['rating']} | Lesiones: {datos['lesiones']} | Pases: {datos['pases']}%")
        
        print("-" * 40)
        
    conexion.close()
    print("¡Actualización masiva terminada!")

# --- EJECUCIÓN DEL SCRIPT ---
if __name__ == "__main__":
    actualizar_base_datos()