@echo off
title KROTTUN — L3 TUN Proxy Manager
cd /d "%~dp0"

net session >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Запуск с правами Администратора...
    python main.py
) else (
    echo [INFO] Запрос прав Администратора для сетевого TUN-драйвера...
    powershell -Command "Start-Process python -ArgumentList '\"%~dp0main.py\"' -Verb RunAs -WorkingDirectory '\"%~dp0\"'"
)
