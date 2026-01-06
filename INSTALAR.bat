@echo off
chcp 65001 >nul
title Instalador SENAPRED Monitor v5

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║           INSTALADOR - Monitor SENAPRED v5.0                 ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

echo [1/3] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo X ERROR: Python no esta instalado
    echo    Descargalo de: https://www.python.org/downloads/
    echo    IMPORTANTE: Marca "Add Python to PATH" durante la instalacion
    pause
    exit /b 1
)
echo OK Python encontrado

echo.
echo [2/3] Instalando dependencias...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt

echo.
echo [3/3] Verificando instalacion...
python -c "from selenium import webdriver; print('OK Selenium')"
python -c "from bs4 import BeautifulSoup; print('OK BeautifulSoup')"
python -c "from plyer import notification; print('OK Plyer')"

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║              INSTALACION COMPLETADA                          ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo USO:
echo   python monitor_senapred.py                    (ver alertas)
echo   python monitor_senapred.py --monitor --sound  (monitoreo)
echo   python monitor_senapred.py --dias 7           (ultimos 7 dias)
echo.
echo O ejecuta: INICIAR_MONITOR.bat
echo.
pause
