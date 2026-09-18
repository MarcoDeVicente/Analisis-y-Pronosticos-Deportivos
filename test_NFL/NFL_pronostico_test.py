import nfl_data_py as nfl
import sqlite3
import pandas as pd

def calcular_eficiencia_epa():
    print("🏈 Conectando con nflverse para extraer histórico (2025) y actual (2026)...")
    
    try:
        # 1. Descargamos 2025 y 2026 juntos (Tomará entre 1 y 2 minutos)
        print("📡 Descargando jugadas... (Paciencia, son más de 50,000 registros)")
        df_pbp = nfl.import_pbp_data([2025, 2026])
        
        print("🧮 Calculando Promedio Ponderado de EPA...")
        jugadas_reales = df_pbp[df_pbp['play_type'].isin(['pass', 'run'])]
        
        # --- OFENSIVA: Agrupamos por Equipo y Temporada ---
        epa_off = jugadas_reales.groupby(['posteam', 'season'])['epa'].mean().reset_index()
        # Pivotamos para que 2025 y 2026 sean columnas separadas
        epa_off = epa_off.pivot(index='posteam', columns='season', values='epa').reset_index()
        epa_off.rename(columns={'posteam': 'equipo', 2025: 'off_2025', 2026: 'off_2026'}, inplace=True)
        epa_off.fillna(0, inplace=True) # Limpieza de seguridad
        
        # --- DEFENSIVA: Agrupamos por Equipo y Temporada ---
        epa_def = jugadas_reales.groupby(['defteam', 'season'])['epa'].mean().reset_index()
        epa_def = epa_def.pivot(index='defteam', columns='season', values='epa').reset_index()
        epa_def.rename(columns={'defteam': 'equipo', 2025: 'def_2025', 2026: 'def_2026'}, inplace=True)
        epa_def.fillna(0, inplace=True)
        
        # Unimos ambas tablas
        df_epa = pd.merge(epa_off, epa_def, on='equipo')
        
        # --- EL CÁLCULO PONDERADO (BLENDING) ---
        # Al estar a mediados de Septiembre, la muestra de 2026 es muy pequeña.
        # Le damos un peso del 70% a la temporada pasada y 30% a la actual.
        PESO_2025 = 0.70
        PESO_2026 = 0.30
        
        df_epa['epa_ofensivo'] = (df_epa['off_2025'] * PESO_2025) + (df_epa['off_2026'] * PESO_2026)
        df_epa['epa_defensivo'] = (df_epa['def_2025'] * PESO_2025) + (df_epa['def_2026'] * PESO_2026)
        
        # Ordenamos para mostrar en consola y comprobar que funciona
        df_epa = df_epa.sort_values(by='epa_ofensivo', ascending=False)
        print("\n🏆 Top 5 Ofensivas (Promedio Ponderado 70/30):")
        # Mostramos cómo la fórmula "castiga" o "premia" usando el histórico
        print(df_epa[['equipo', 'epa_ofensivo', 'off_2025', 'off_2026']].head(5).to_string(index=False))
        
        # --- GUARDAR EN SQLITE ---
        print("\n💾 Inyectando métricas estabilizadas en DB-NFL-Test.db...")
        # Filtramos solo las columnas que necesita tu motor matemático
        columnas_finales = ['equipo', 'epa_ofensivo', 'epa_defensivo']
        df_final = df_epa[columnas_finales]
        
        conexion = sqlite3.connect("DB-NFL-Test.db")
        df_final.to_sql('nfl_eficiencia_epa', conexion, if_exists='replace', index=False)
        conexion.close()
        
        print("✅ ¡Base de datos actualizada con Inteligencia Contextual!")
        
    except Exception as e:
        print(f"⚠️ Error: {e}")

if __name__ == "__main__":
    calcular_eficiencia_epa()