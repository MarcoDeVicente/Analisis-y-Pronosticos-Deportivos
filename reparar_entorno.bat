@echo off
title Reparador de Entorno - Pronosticos IA
echo ===================================================
echo     PRONOSTICOS IA - REPARADOR DE ENTORNO VIRTUAL
echo ===================================================
echo.
echo Este script creara un nuevo entorno virtual y descargara
echo las librerias necesarias para que el sistema vuelva a funcionar.
echo.
echo Asegurate de tener Python instalado (desde python.org o la Microsoft Store).
echo.
pause

echo.
echo [1/4] Verificando Python...
python --version
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] No se detecta Python. Por favor, instala Python 3.10 o superior.
    echo Asegurate de marcar la casilla "Add Python to PATH" durante la instalacion.
    pause
    exit /b
)

echo.
echo [2/4] Eliminando entorno virtual anterior (si existe)...
IF EXIST sklearn-env (
    rmdir /s /q sklearn-env
)
IF EXIST venv (
    rmdir /s /q venv
)

echo.
echo [3/4] Creando nuevo entorno virtual 'sklearn-env'...
python -m venv sklearn-env

echo.
echo [4/4] Instalando dependencias necesarias...
call sklearn-env\Scripts\activate.bat
pip install -r requirements.txt

echo.
echo ===================================================
echo Entorno reparado con exito.
echo ===================================================
echo Ahora puedes ejecutar 'iniciar_pronosticos.bat' normalmente.
pause
exit
