import sqlite3

def predecir_partido_nfl(local, visitante):
    print(f"\n🏈 Analizando: {local} (Local) vs {visitante} (Visitante)")
    
    conexion = sqlite3.connect("DB-NFL-Test.db")
    cursor = conexion.cursor()
    
    # Extraemos el EPA del equipo Local
    cursor.execute("SELECT epa_ofensivo, epa_defensivo FROM nfl_eficiencia_epa WHERE equipo=?", (local,))
    stats_local = cursor.fetchone()
    
    # Extraemos el EPA del equipo Visitante
    cursor.execute("SELECT epa_ofensivo, epa_defensivo FROM nfl_eficiencia_epa WHERE equipo=?", (visitante,))
    stats_visitante = cursor.fetchone()
    
    conexion.close()
    
    if not stats_local or not stats_visitante:
        print("⚠️ Error: Equipo no encontrado. Usa siglas oficiales (ej. 'KC', 'BAL', 'CHI').")
        return
        
    local_off_epa, local_def_epa = stats_local
    visita_off_epa, visita_def_epa = stats_visitante
    
    # --- EL MOTOR MATEMÁTICO ---
    JUGADAS_PROMEDIO = 63.5  # Promedio de jugadas ofensivas por equipo en un partido
    PUNTOS_BASE = 21.0       # Promedio histórico de puntos por equipo en la NFL
    VENTAJA_LOCALIA = 1.5    # El "Home Field Advantage" en la NFL moderna vale ~1.5 puntos
    
    # EPA Neto: Ofensiva propia + Defensiva rival. 
    # (Nota: Un EPA defensivo positivo significa que la defensa es MALA, por lo que SUMA puntos a la ofensiva rival)
    epa_neto_local = local_off_epa + visita_def_epa
    epa_neto_visita = visita_off_epa + local_def_epa
    
    # Cálculo de Puntos Finales
    puntos_local = PUNTOS_BASE + (epa_neto_local * JUGADAS_PROMEDIO) + VENTAJA_LOCALIA
    puntos_visita = PUNTOS_BASE + (epa_neto_visita * JUGADAS_PROMEDIO)
    
    # Evitamos que la muestra pequeña genere puntuaciones irreales
    puntos_local = max(3.0, round(puntos_local, 1))
    puntos_visita = max(3.0, round(puntos_visita, 1))
    
    # --- CÁLCULO DE APUESTAS (SPREAD Y MONEYLINE) ---
    # El Spread siempre se expresa desde la perspectiva del favorito (negativo)
    margen_victoria = puntos_local - puntos_visita
    spread_local = round(-margen_victoria * 2) / 2  # Redondeamos a mitades (ej. -3.0, -3.5)
    
    total_puntos = puntos_local + puntos_visita
    
    # Transformación del margen a Probabilidad de Victoria (Modelo Elo / Sigmoide)
    # En la NFL, una ventaja de 1 punto en el spread equivale a un ~3.3% extra de ganar
    prob_local = (1 / (1 + 10 ** (-margen_victoria / 15))) * 100
    prob_visita = 100 - prob_local
    
    # --- IMPRESIÓN DE RESULTADOS ---
    print("-" * 45)
    print(f"🎯 Puntos Proyectados:")
    print(f"   ➤ {local}: {puntos_local}")
    print(f"   ➤ {visitante}: {puntos_visita}")
    print("-" * 45)
    print(f"📊 Línea de Apuesta (Spread): {local} {'+' if spread_local > 0 else ''}{spread_local}")
    print(f"📈 Over / Under: {round(total_puntos, 1)} puntos totales")
    print(f"🏆 Probabilidad de Victoria (Moneyline):")
    print(f"   {local}: {round(prob_local, 1)}%")
    print(f"   {visitante}: {round(prob_visita, 1)}%")

if __name__ == "__main__":
    # Puedes cambiar los equipos aquí. (Usa: BAL, KC, SF, PHI, DAL, CHI, etc.)
    predecir_partido_nfl("DET", "BUF")
    predecir_partido_nfl("CAR", "ATL")
    