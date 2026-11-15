@echo off
REM run_daily.bat - Script para ejecutar el pipeline de Cuy automáticamente desde el Programador de Tareas

cd /d "%~dp0"
echo ======================================================== >> cron_log.txt
echo [%date% %time%] Iniciando pipeline autonomo programado... >> cron_log.txt
echo ======================================================== >> cron_log.txt

call .venv\Scripts\python.exe generate_and_assemble_episode.py random kimi -a cuy >> cron_log.txt 2>&1

echo [%date% %time%] Pipeline finalizado con codigo de salida: %ERRORLEVEL% >> cron_log.txt
echo. >> cron_log.txt
