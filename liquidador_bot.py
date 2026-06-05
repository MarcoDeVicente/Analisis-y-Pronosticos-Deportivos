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
        equipo_local = row['Local']
        inversion = row['Inversion_Simulada']
        ganancia_potencial = row['Ganancia_Potencial']
        
        gano_el_local_en_la_vida_real = True if row['Prob_IA_Local'] > 60.0 else False 
        
        if gano_el_local_en_la_vida_real:
            nuevo_estado = 'Ganada'
            # Si ganas, recuperas tu inversión + la ganancia del momio
            retorno_real = ganancia_potencial
            beneficio_neto = retorno_real - inversion
            ganancia_neta_total += beneficio_neto
            print(f" ¡GANADA! {partido} -> +${beneficio_neto:.2f}")
        else:
            nuevo_estado = 'Perdida'
            # Si pierdes, tu retorno es 0 y tu pérdida es la inversión completa
            retorno_real = 0.0
            ganancia_neta_total -= inversion
            print(f" PERDIDA. {partido} -> -${inversion:.2f}")
            
       
        cursor.execute("""
            UPDATE bot_portafolio 
            SET Estado = ?, Ganancia_Potencial = ? 
            WHERE Partido = ? AND Estado = 'Pendiente'
        """, (nuevo_estado, retorno_real, partido))
        
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

# Ejecuta el liquidador
if __name__ == "__main__":
    liquidar_inversiones()