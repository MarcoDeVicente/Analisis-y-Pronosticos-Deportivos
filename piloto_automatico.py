import schedule
import time
from datetime import datetime

# Importamos las funciones que creaste en los archivos anteriores
# Asegúrate de que los nombres de los archivos y funciones coincidan con los tuyos
from bot_financiero import obtener_momios_en_vivo, analizar_value_bets, registrar_inversiones_simuladas
from liquidador_bot import liquidar_inversiones

def rutina_diaria_de_trading():
    hora_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("\n" + "="*60)
    print(f"INICIANDO RUTINA DE TRADING AUTOMÁTICA | {hora_actual}")
    print("="*60)

    # PASO 1: Liquidar las inversiones del día anterior
    liquidar_inversiones()

    print("-" * 60)

    # Extraemos el mercado y cruzamos con la IA
    df_mercado = obtener_momios_en_vivo("baseball_mlb")
    
    if df_mercado is not None and not df_mercado.empty:
        df_inversiones = analizar_value_bets(df_mercado)
        
        
        if not df_inversiones.empty:
            registrar_inversiones_simuladas(df_inversiones)
            
    print("\n Rutina terminada con éxito. El bot entra en modo reposo.")

# Las 10:00 AM es buena hora porque los casinos ya publicaron sus momios del día.
schedule.every().day.at("10:00").do(rutina_diaria_de_trading)

print(" Sistema de trading algorítmico en línea.")
print(" Esperando la hora programada (10:00 AM) para operar...")

# Este es el ciclo infinito que mantiene al bot vivo
while True:
    schedule.run_pending()
    time.sleep(600) # El bot revisa el reloj cada 10 minutos para no agotar el CPU de tu computadora