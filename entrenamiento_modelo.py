import pandas as pd
import numpy as np
from scipy.stats import poisson 
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Si no la guardaste como CSV, puedes traerte el DataFrame df_equipos directamente aquí
try:
    df = pd.read_csv('Dataset_Futbol_ML.csv')
except FileNotFoundError:
    print("Error: No se encontró la matriz. Asegúrate de exportar dataset_final a CSV en el script anterior.")
    exit()

# 2. Separar las Variables (X) y el Resultado a predecir (y)
X = df[['Local_GF_Prom', 'Local_GC_Prom', 'Visita_GF_Prom', 'Visita_GC_Prom']]
y = df['Target_Ganador']

# Dividir datos: 80% para estudiar, 20% para examen
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 3. ENTRENAR EL MODELO (Random Forest)
print("Entrenando la red neuronal (Random Forest)...")
modelo_victoria = RandomForestClassifier(n_estimators=100, random_state=42)
modelo_victoria.fit(X_train, y_train)

# Evaluar qué tan inteligente se volvió el modelo
precision = accuracy_score(y_test, modelo_victoria.predict(X_test))
print(f"Precision del modelo en datos historicos: {precision * 100:.1f}%\n")

# ==========================================
# SIMULACIÓN DE LA FINAL: PSG vs ARSENAL
# ==========================================
print("--- PREDICCION FINAL CHAMPIONS LEAGUE ---")

# (Datos de ejemplo basados en tu base de datos)
# Supongamos que el PSG promedia 2.8 GF y 0.8 GC, y Arsenal 2.2 GF y 0.9 GC
datos_final = pd.DataFrame({
    'Local_GF_Prom': [2.8],
    'Local_GC_Prom': [0.8],
    'Visita_GF_Prom': [2.2],
    'Visita_GC_Prom': [0.9]
})

# A. Predicción de Victoria (Machine Learning)
probabilidades = modelo_victoria.predict_proba(datos_final)[0]
print(f"Probabilidad Victoria PSG: {probabilidades[1]*100:.1f}%") # Target 1
print(f"Probabilidad Empate:       {probabilidades[0]*100:.1f}%") # Target 0
print(f"Probabilidad Victoria ARS: {probabilidades[2]*100:.1f}%") # Target 2

# B. Predicción de Marcador (Distribución de Poisson)
# Usamos el ataque de uno contra la defensa del otro para ajustar el Promedio de Goles Esperados
xg_psg = (2.8 + 0.9) / 2
xg_ars = (2.2 + 0.8) / 2

print(f"\nGoles Esperados: PSG ({xg_psg:.2f}) vs Arsenal ({xg_ars:.2f})")

print("\nMatriz de Marcadores Probables (Top 5):")
marcadores = []
for goles_psg in range(5):
    for goles_ars in range(5):
        # Multiplicamos la probabilidad de que el PSG meta 'x' goles por la del Arsenal metiendo 'y' goles
        prob_marcador = poisson.pmf(goles_psg, xg_psg) * poisson.pmf(goles_ars, xg_ars)
        marcadores.append( (f"{goles_psg} - {goles_ars}", prob_marcador) )

# Ordenar de mayor a menor probabilidad y mostrar los 5 más seguros
marcadores.sort(key=lambda x: x[1], reverse=True)
for marcador, prob in marcadores[:5]:
    print(f"Resultado {marcador}: {prob*100:.1f}%")

# ── Cargar datos ──────────────────────────────────────────────────────────────
df = pd.read_csv("E0-2.csv") 
df = pd.read_csv("F1-2.csv")  
df = pd.read_csv("UCL_2025_26.csv")  

# ── Promedios globales de la liga ─────────────────────────────────────────────
avg_hc = df["HC"].mean()   # promedio de corners local en la liga
avg_ac = df["AC"].mean()   # promedio de corners visitante en la liga

# ── Calcular fuerza atacante y debilidad defensiva por equipo ─────────────────
equipos = pd.concat([df["Home"], df["Away"]]).unique()

stats = {}
for eq in equipos:
    como_local    = df[df["Home"] == eq]
    como_visitante = df[df["Away"] == eq]

    # Corners a favor (ataque de corners)
    hc_atq = como_local["HC"].mean()   / avg_hc   # fuerza generando corners en casa
    ac_atq = como_visitante["AC"].mean() / avg_ac  # fuerza generando corners fuera

    # Corners en contra (defensa, qué tanto permite al rival sacar corners)
    hc_def = como_local["AC"].mean()   / avg_ac   # debilidad defensiva en casa
    ac_def = como_visitante["HC"].mean() / avg_hc  # debilidad defensiva de visitante

    stats[eq] = {
        "atq_local":   hc_atq,
        "atq_visit":   ac_atq,
        "def_local":   hc_def,   # cuántos corners concede cuando es local
        "def_visit":   ac_def,   # cuántos corners concede cuando es visitante
    }

# ── 1. Cargar y unir los tres CSV ─────────────────────────────────────────────
df_e0  = pd.read_csv("E0-2.csv")
df_f1  = pd.read_csv("F1-2.csv")
df_ucl = pd.read_csv("UCL_2025_26.csv")

# Quedarse solo con las columnas necesarias (por si tienen columnas distintas)
cols = ["Home", "Away", "HC", "AC"]
df = pd.concat([
    df_e0[cols],
    df_f1[cols],
    df_ucl[cols]
], ignore_index=True).dropna(subset=["HC", "AC"])

# ── 2. Verificar nombres exactos de los equipos ───────────────────────────────
equipos = sorted(pd.concat([df["Home"], df["Away"]]).unique())
print("Equipos disponibles en los datos:")
for e in equipos:
    print(f"  '{e}'")

# ── 3. Promedios globales de la liga ──────────────────────────────────────────
avg_hc = df["HC"].mean()
avg_ac = df["AC"].mean()
print(f"\nPromedio corners local (liga): {avg_hc:.2f}")
print(f"Promedio corners visitante (liga): {avg_ac:.2f}")

# ── 4. Calcular stats por equipo ──────────────────────────────────────────────
stats = {}
for eq in equipos:
    local     = df[df["Home"] == eq]
    visitante = df[df["Away"] == eq]

    # Si el equipo tiene menos de 3 partidos, saltar para evitar promedios poco fiables
    if len(local) < 3 and len(visitante) < 3:
        continue

    stats[eq] = {
        "atq_local":  (local["HC"].mean()      / avg_hc)  if len(local)     > 0 else 1.0,
        "atq_visit":  (visitante["AC"].mean()  / avg_ac)  if len(visitante) > 0 else 1.0,
        "def_local":  (local["AC"].mean()      / avg_ac)  if len(local)     > 0 else 1.0,
        "def_visit":  (visitante["HC"].mean()  / avg_hc)  if len(visitante) > 0 else 1.0,
    }

# ── 5. Función de predicción ──────────────────────────────────────────────────
def predecir_corners(local, visitante, stats, avg_hc, avg_ac, top_n=5):

    # Validar que ambos equipos existen
    for eq in [local, visitante]:
        if eq not in stats:
            equipos_similares = [e for e in stats if eq.lower() in e.lower()]
            print(f"\n❌ '{eq}' no encontrado en stats.")
            if equipos_similares:
                print(f"   ¿Quisiste decir? {equipos_similares}")
            return

    lam_local = stats[local]["atq_local"]    * stats[visitante]["def_visit"] * avg_hc
    lam_visit = stats[visitante]["atq_visit"] * stats[local]["def_local"]    * avg_ac

    print(f"\ncorners {local} (local):     {lam_local:.2f}")
    print(f"corners {visitante} (visitante): {lam_visit:.2f}")
    print(f"Total esperado en el partido:   {lam_local + lam_visit:.2f}")

    # Distribución conjunta
    max_c = 20
    dist = {}
    for h in range(max_c):
        for a in range(max_c):
            dist[(h, a)] = poisson.pmf(h, lam_local) * poisson.pmf(a, lam_visit)

    top5 = sorted(dist.items(), key=lambda x: x[1], reverse=True)[:top_n]
    print(f"\nTop {top_n} marcadores de corners mas probables:")
    for (h, a), prob in top5:
        print(f"  {local} {h} - {a} {visitante}:  {prob*100:.2f}%") 

    # Mercados Over/Under
    lam_total = lam_local + lam_visit
    print("\nMercados Over/Under:")
    for linea in [7.5, 8.5, 9.5, 10.5, 11.5]:
        over = (1 - poisson.cdf(int(linea), lam_total)) * 100
        print(f"  Over  {linea}: {over:.1f}%  |  Under {linea}: {100 - over:.1f}%")

# ── 6. Predicción final Champions League ─────────────────────────────────────
# Usa los nombres EXACTOS que apareció en el print de equipos del paso 2
predecir_corners("Paris SG", "Arsenal", stats, avg_hc, avg_ac)