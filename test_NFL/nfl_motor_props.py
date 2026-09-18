import sqlite3
import statistics

def analizar_prop_avanzado(jugador, estadistica, linea_casino, equipo_rival):
    print(f"\n📊 Analizando: {jugador} - {estadistica} vs {equipo_rival} (Línea: {linea_casino})")
    
    conexion = sqlite3.connect("DB-NFL-Test.db")
    cursor = conexion.cursor()
    
    # 1. Extraemos el historial del jugador
    query_jugador = f"SELECT {estadistica} FROM nfl_jugadores_stats WHERE jugador = ?"
    cursor.execute(query_jugador, (jugador,))
    resultados = cursor.fetchall()
    
    # 2. Extraemos el poder de la defensa rival (EPA Defensivo)
    cursor.execute("SELECT epa_defensivo FROM nfl_eficiencia_epa WHERE equipo = ?", (equipo_rival,))
    stats_rival = cursor.fetchone()
    
    conexion.close()
    
    if not resultados:
        print("⚠️ Jugador no encontrado.")
        return
    if not stats_rival:
        print(f"⚠️ Equipo rival '{equipo_rival}' no encontrado. Usa siglas (ej. 'CAR', 'CLE').")
        return
        
    historial = [fila[0] for fila in resultados]
    partidos_jugados = len(historial)
    epa_defensivo_rival = stats_rival[0]
    
    if partidos_jugados < 5:
        print(f"⚠️ Muestra muy pequeña ({partidos_jugados} partidos).")
        return
        
    # --- MATEMÁTICA BASE ---
    promedio_base = statistics.mean(historial)
    desviacion_base = statistics.stdev(historial)
    
    # --- INTELIGENCIA DE MATCHUP (AJUSTE POR RIVAL) ---
    # Un EPA defensivo mayor a 0 es malo para la defensa (bueno para el jugador).
    # Escala: Cada 0.1 de EPA mueve la proyección del jugador un ~12%.
    factor_ajuste = epa_defensivo_rival * 1.2
    multiplicador = 1 + factor_ajuste
    
    # Limitamos el multiplicador para evitar proyecciones irreales (Max +25%, Min -25%)
    multiplicador = max(0.75, min(1.25, multiplicador))
    
    promedio_ajustado = promedio_base * multiplicador
    desviacion_ajustada = desviacion_base * multiplicador
    
    # --- CÁLCULO DE PROBABILIDAD (CAMPANA DE GAUSS) ---
    distribucion = statistics.NormalDist(promedio_ajustado, desviacion_ajustada)
    prob_under = distribucion.cdf(linea_casino) * 100
    prob_over = 100 - prob_under
    
    # --- IMPRESIÓN DE DIAGNÓSTICO ---
    print("-" * 50)
    print(f"🎯 Promedio Histórico: {round(promedio_base, 1)} {estadistica}")
    
    # Mostrar el efecto de la defensa visualmente
    if multiplicador > 1.0:
        print(f"🛡️ Defensa Rival ({equipo_rival}): DÉBIL (Ajuste: +{round((multiplicador-1)*100, 1)}%)")
    else:
        print(f"🛡️ Defensa Rival ({equipo_rival}): ELITE (Ajuste: -{round((1-multiplicador)*100, 1)}%)")
        
    print(f"🔥 PROYECCIÓN FINAL: {round(promedio_ajustado, 1)} {estadistica} (Volatilidad: ±{round(desviacion_ajustada, 1)})")
    print("-" * 50)
    print(f"💰 PROB. OVER  (+{linea_casino}): {round(prob_over, 1)}%")
    print(f"💰 PROB. UNDER (-{linea_casino}): {round(prob_under, 1)}%")
    print("-" * 50)
    
    if prob_over > 58.0:
        print(f"✅ VALUE BET: Fuerte tendencia al OVER. El casino no está considerando lo débil que es {equipo_rival}.")
    elif prob_under > 58.0:
        print(f"✅ VALUE BET: Fuerte tendencia al UNDER. El casino subestima a la defensa de {equipo_rival}.")
    else:
        print("⚖️ Línea eficiente. EV 0.")

if __name__ == "__main__":
    # Vamos a probar cómo cambia Lamar Jackson si juega contra una defensa TERRIBLE (JAX) vs una ELITE (CHI)
    
    # 1. Lamar contra Jacksonville (Defensa muy mala, EPA positivo alto)
    analizar_prop_avanzado("L.Jackson", "rushing_yards", 50.5, "JAX")
    
    # 2. Lamar contra Chicago (Defensa élite, EPA negativo)
    analizar_prop_avanzado("L.Jackson", "rushing_yards", 50.5, "CHI")