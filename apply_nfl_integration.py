import re

# 1. Update index.html
with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

old_sync_js = """                    const res = await fetch(`${API_BASE}/sync/nfl`, { method: 'POST' });
                    if (res.ok) {
                        const data = await res.json();
                        if (statusDiv) {
                            statusDiv.className = "mt-4 text-xs font-semibold text-emerald-400";
                            statusDiv.innerHTML = `¡Datos de la NFL sincronizados con éxito!<br><span class="text-slate-400 text-[10px]">Agregados: ${data.games_synced} partidos | ${data.players_added} estadísticas de jugadores</span>`;
                        }
                        showPremiumToast("🏈 Datos de la NFL sincronizados con éxito.");
                        fetchAdminStats(); // Refresh the stats after sync
                    }"""

new_sync_js = """                    const res = await fetch(`${API_BASE}/sync/nfl`, { method: 'POST' });
                    if (res.ok) {
                        const data = await res.json();
                        if (statusDiv) {
                            statusDiv.className = "mt-4 text-xs font-semibold text-blue-400";
                            statusDiv.innerHTML = `¡Sincronización de NFL iniciada en segundo plano!<br><span class="text-slate-400 text-[10px]">Los datos estarán disponibles en unos minutos. Refresca la página más tarde.</span>`;
                        }
                        showPremiumToast("🏈 Sincronización iniciada en 2do plano.");
                    }"""

if old_sync_js in html:
    html = html.replace(old_sync_js, new_sync_js)
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("index.html updated.")
else:
    print("Could not find old_sync_js in index.html")

# 2. Update api_deportes.py
with open('api_deportes.py', 'r', encoding='utf-8') as f:
    api = f.read()

old_nfl_sync = """@app.post("/api/sync/nfl")
def sync_nfl_data():
    try:
        import time
        time.sleep(1.5) # Simular tiempo de petición a API
        
        # Simular base de datos update
        import random
        games = random.randint(3, 12)
        players = games * random.randint(15, 30)
        
        return {
            "status": "success", 
            "message": "Datos de la NFL sincronizados con éxito",
            "games_synced": games,
            "players_added": players
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))"""

new_nfl_sync = """from nfl_logic import sincronizar_datos_nfl, predecir_partido_nfl, analizar_prop_nfl

@app.post("/api/sync/nfl")
def sync_nfl_data(background_tasks: BackgroundTasks):
    try:
        # Ejecutar en segundo plano
        background_tasks.add_task(sincronizar_datos_nfl)
        
        return {
            "status": "processing", 
            "message": "Sincronización de NFL iniciada en segundo plano."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/nfl/partidos/predecir")
def get_nfl_prediccion(local: str, visitante: str):
    try:
        resultado = predecir_partido_nfl(local, visitante)
        if not resultado:
            raise HTTPException(status_code=404, detail="Equipos no encontrados en nfl_eficiencia_epa")
        return {"status": "success", "data": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/nfl/props/analizar")
def get_nfl_prop(jugador: str, stat: str, linea: float, rival: str):
    try:
        resultado = analizar_prop_nfl(jugador, stat, linea, rival)
        if "error" in resultado:
            # 422 Unprocessable Entity si la muestra es insuficiente o 404 si no se encuentra
            status_code = 422 if "insuficiente" in resultado["error"] else 404
            raise HTTPException(status_code=status_code, detail=resultado["error"])
        return {"status": "success", "data": resultado}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))"""

if old_nfl_sync in api:
    api = api.replace(old_nfl_sync, new_nfl_sync)
    with open('api_deportes.py', 'w', encoding='utf-8') as f:
        f.write(api)
    print("api_deportes.py updated.")
else:
    print("Could not find old_nfl_sync in api_deportes.py")
