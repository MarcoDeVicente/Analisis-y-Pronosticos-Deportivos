import pandas as pd
import os
import numpy as np

def agregar_probs_cuotas(df):
    columnas_generadas = []
    for prefix in ['PSC', 'MaxC', 'AvgC']:
        h_col = f'{prefix}H'
        d_col = f'{prefix}D'
        a_col = f'{prefix}A'

        if all(c in df.columns for c in [h_col, d_col, a_col]):
            # Replace 0 with NaN to avoid division by zero
            df[h_col] = df[h_col].replace(0, np.nan)
            df[d_col] = df[d_col].replace(0, np.nan)
            df[a_col] = df[a_col].replace(0, np.nan)

            # Probabilidad bruta (inverso de la cuota)
            prob_h = 1 / df[h_col]
            prob_d = 1 / df[d_col]
            prob_a = 1 / df[a_col]

            # Suma total — siempre > 1 por el margen de la casa
            total = prob_h + prob_d + prob_a

            # Probabilidades normalizadas a 100% y redondeo a 6 decimales
            col_ph = f'prob_H_{prefix}'
            col_pd = f'prob_D_{prefix}'
            col_pa = f'prob_A_{prefix}'
            col_vig = f'vig_{prefix}'

            df[col_ph] = (prob_h / total).round(6)
            df[col_pd] = (prob_d / total).round(6)
            df[col_pa] = (prob_a / total).round(6)

            # Margen de la casa (vig) redondeado a 4 decimales
            df[col_vig] = (total - 1).round(4)
            
            columnas_generadas.extend([col_ph, col_pd, col_pa, col_vig])

    return df, columnas_generadas

archivos = [
    ('datos_crudos/E0-2.csv', 'E0-2_odds.xlsx'),
    ('datos_crudos/F1-2.csv', 'F1-2_odds.xlsx'),
    ('datos_crudos/MEX.csv', 'MEX_Liga_Combined_odds.xlsx') 
]

for in_file, out_file in archivos:
    if not os.path.exists(in_file):
        # Try .xlsx if .csv is not found or vice versa
        alt_in_file = in_file.replace('.csv', '.xlsx')
        if os.path.exists(alt_in_file):
            in_file = alt_in_file
        else:
            print(f"Archivo no encontrado: {in_file}")
            continue
            
    print(f"Procesando {in_file}...")
    if in_file.endswith('.csv'):
        df = pd.read_csv(in_file)
    else:
        df = pd.read_excel(in_file)
        
    total_filas = len(df)
    
    df, cols_gen = agregar_probs_cuotas(df)
    
    if cols_gen:
        # Check rows with complete data vs any NaN in generated columns
        completas = df[cols_gen].dropna().shape[0]
        con_nan = total_filas - completas
    else:
        completas = 0
        con_nan = total_filas
        
    df.to_excel(out_file, index=False)
    
    print(f"--- Resumen {out_file} ---")
    print(f"Total filas procesadas: {total_filas}")
    print(f"Filas con las {len(cols_gen)} columnas completas (sin NaN): {completas}")
    print(f"Filas con algun NaN en las nuevas columnas: {con_nan}")
    print(f"Columnas nuevas generadas: {cols_gen}\n")
