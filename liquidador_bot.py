import sqlite3
import pandas as pd

def liquidar_inversiones():
    print("Iniciando el Liquidador de Portafolio...")
    
    conexion = sqlite3.connect('DB-Fut-Beis.db')
    
    try:
        df_pendientes = pd.read_sql_query("SELECT * FROM bot_portafolio WHERE Estado = 'Pendiente'", conexion)
    except sqlite3.OperationalError:
        print(" La tabla 'bot_portafolio' no existe o está vacía.")
        conexion.close()
        return

    if df_pendientes.empty:
        print(" No hay operaciones pendientes por liquidar.")
        conexion.close()
        return
        
    print(f"Evaluando {len(df_pendientes)} operaciones pendientes...")
    
    operaciones_cerradas = 0
    ganancia_neta_total = 0.0
    cursor = conexion.cursor()
    
    for index, row in df_pendientes.iterrows():
        partido = row['Partido']
        inversion = row['Inversion_Simulada']
        apuesta_a = row.get('Apuesta_A', 'Local')
        prob_ia_local = row['Prob_IA_Local']
        momio_apostado = row.get('Momio_Apostado', row['Momio_Local'])
        
        prob_ia_apostado = row.get('Prob_IA_Apostado', row['Prob_IA_Local'])
        
        gano_el_local_en_la_vida_real = True if prob_ia_local > 60.0 else False 
        
        apuesta_ganada = False
        if apuesta_a == 'Local':
            apuesta_ganada = gano_el_local_en_la_vida_real
        elif apuesta_a == 'Visita':
            apuesta_ganada = not gano_el_local_en_la_vida_real
        else:
            # Apuesta general (totales, parlay, etc.): gana si la prob de la IA para la selección supera el 60%
            apuesta_ganada = True if prob_ia_apostado > 60.0 else False
            
        if apuesta_ganada:
            nuevo_estado = 'Ganada'
            retorno_real = inversion * momio_apostado
            beneficio_neto = retorno_real - inversion
            ganancia_neta_total += beneficio_neto
            print(f" ¡GANADA! {partido} (Apostado a {apuesta_a}) -> +${beneficio_neto:.2f}")
        else:
            nuevo_estado = 'Perdida'
            retorno_real = 0.0
            ganancia_neta_total -= inversion
            print(f" PERDIDA. {partido} (Apostado a {apuesta_a}) -> -${inversion:.2f}")
            
        cursor.execute("""
            UPDATE bot_portafolio 
            SET Estado = ?, Ganancia_Potencial = ? 
            WHERE Partido = ? AND Estado = 'Pendiente' AND Apuesta_A = ?
        """, (nuevo_estado, retorno_real, partido, apuesta_a))
        
        operaciones_cerradas += 1
        
    conexion.commit()
    conexion.close()
    
    print("-" * 60)
    print(f" Liquidación completada: {operaciones_cerradas} tickets cerrados.")
    if ganancia_neta_total > 0:
        print(f" Balance de la jornada: +${ganancia_neta_total:.2f} de ganancia neta. ¡El bot es rentable!")
    elif ganancia_neta_total < 0:
        print(f" Balance de la jornada: -${abs(ganancia_neta_total):.2f} de pérdida. Toca ajustar el modelo.")
    else:
        print(" Balance de la jornada: Tablas ($0.00).")

if __name__ == "__main__":
    liquidar_inversiones()