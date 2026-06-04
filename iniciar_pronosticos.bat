@echo off
title Pronosticos IA - Iniciando Servidor...
echo ===================================================
echo     PRONOSTICOS IA - CONFIGURADOR DE BACKEND     
echo ===================================================
echo.
echo [1/2] Iniciando el servidor FastAPI de Uvicorn...
echo.

:: Launch FastAPI backend minimized so it doesn't block the screen
start "FastAPI Backend" /min ".\sklearn-env\Scripts\python.exe" -m uvicorn api_deportes:app --port 8000 --reload

echo [2/2] Esperando a que el puerto 8000 este listo...
timeout /t 3 /nobreak >nul

echo.
echo [OK] Abriendo la interfaz en tu navegador predeterminado...
start "" "index.html"

echo.
echo Todo listo. Puedes cerrar esta ventana.
timeout /t 2 >nul
exit
