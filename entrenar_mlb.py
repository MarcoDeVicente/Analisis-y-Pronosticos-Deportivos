import pandas as pd
import numpy as np
from scipy.stats import poisson
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# 1. Cargar la Matriz de Entrenamiento
try:
    df = pd.read_csv('Dataset_Beisbol_ML.csv')
except FileNotFoundError:
    print("Error: No se encontró el dataset. Asegúrate de estar en la carpeta correcta.")
    exit()

# 2. Separar Variables (X) y el Resultado (y)
X = df[['Local_Pitcher_ERA', 'Local_Pitcher_K', 'Local_Bateo_Prom', 
        'Visita_Pitcher_ERA', 'Visita_Pitcher_K', 'Visita_Bateo_Prom']]
y = df['Target_Ganador']

# 80% para entrenar, 20% para examen
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 3. ENTRENAR EL MODELO (Random Forest)
print("Entrenando la red neuronal de Beisbol...")
modelo_mlb = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
modelo_mlb.fit(X_train, y_train)

precision = accuracy_score(y_test, modelo_mlb.predict(X_test))
print(f"Precision del modelo en datos historicos: {precision * 100:.1f}%\n")

# ==========================================
# SIMULACIÓN DE PARTIDO: YANKEES VS ORIOLES
# ==========================================
print("--- PREDICCIoN DE PARTIDO MLB ---")
equipo_local = "New York Yankees"
equipo_visita = "Baltimore Orioles"

# Inventamos estadísticas basadas en tu base de datos reciente
# Yankees: Batean 4.14, Pitcher Local (ej. Gerrit Cole) ERA 2.45, 7.0 K
# Orioles: Batean 3.00, Pitcher Visita (ej. Corbin Burnes) ERA 3.33, 5.3 K
datos_hoy = pd.DataFrame({
    'Local_Pitcher_ERA': [2.45], 'Local_Pitcher_K': [7.0], 'Local_Bateo_Prom': [4.14],
    'Visita_Pitcher_ERA': [3.33], 'Visita_Pitcher_K': [5.3], 'Visita_Bateo_Prom': [3.00]
})

# A. Predicción de Victoria
probabilidades = modelo_mlb.predict_proba(datos_hoy)[0]
prob_visita = probabilidades[0] * 100
prob_local = probabilidades[1] * 100

print(f"Probabilidad {equipo_local} (Local): {prob_local:.1f}%")
print(f"Probabilidad {equipo_visita} (Visita): {prob_visita:.1f}%")

# B. Predicción de Carreras (Poisson)
# Ajustamos el bateo del equipo enfrentándolo a la efectividad (ERA) del pitcher rival
carreras_esp_local = (4.14 + 3.33) / 2  # Bateo NYY vs ERA BAL
carreras_esp_visita = (3.00 + 2.45) / 2 # Bateo BAL vs ERA NYY

total_carreras = carreras_esp_local + carreras_esp_visita
print(f"\nCarreras Esperadas: {equipo_local} ({carreras_esp_local:.2f}) vs {equipo_visita} ({carreras_esp_visita:.2f})")
print(f"Total del partido: {total_carreras:.2f} carreras")

# Calcular Mercado Over/Under 7.5 y 8.5
print("\nMercados de Apuestas (Carreras Totales):")
for linea in [7.5, 8.5, 9.5]:
    over = (1 - poisson.cdf(int(linea), total_carreras)) * 100
    under = 100 - over
    print(f"Linea {linea} -> OVER: {over:.1f}% | UNDER: {under:.1f}%")