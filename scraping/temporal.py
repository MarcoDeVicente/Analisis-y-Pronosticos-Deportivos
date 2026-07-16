import requests

# Recuerda poner tu API Key real
API_KEY = "089c43a367c9d806cbb3a278e2461925"
HEADERS = {
    "x-apisports-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

def extraer_ids_mundial():
    # Usamos 2022 para asegurar que el plan gratuito nos deje pasar
    # Si lograste activar un plan superior para 2026, cambia el año a 2026
    LIGA_MUNDIAL = 1
    TEMPORADA = 2026
    
    url = f"https://v3.football.api-sports.io/teams?league={LIGA_MUNDIAL}&season={TEMPORADA}"
    
    print(f" Buscando equipos del Mundial (Temporada {TEMPORADA})...")
    
    try:
        respuesta = requests.get(url, headers=HEADERS)
        datos = respuesta.json()
        
        if datos.get('errors'):
            print(f" Error de la API: {datos['errors']}")
            return
            
        equipos = datos.get('response', [])
        
        if not equipos:
            print(" No se encontraron equipos. Revisa el año o la conexión.")
            return
            
        lista_ids = []
        
        print(f"\nSe encontraron {len(equipos)} equipos:")
        print("-" * 30)
        
        for item in equipos:
            id_equipo = item['team']['id']
            nombre = item['team']['name']
            lista_ids.append(id_equipo)
            
            # Imprime el nombre y su ID para que los tengas de referencia
            print(f"{nombre.ljust(20)} -> ID: {id_equipo}")
            
        print("-" * 30)
        print("\nLISTA LISTA PARA COPIAR Y PEGAR EN TU SCRIPT:")
        print(f"EQUIPOS_MUNDIAL_IDS = {lista_ids}\n")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    extraer_ids_mundial()