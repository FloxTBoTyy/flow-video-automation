#!/usr/bin/env bash
# run_daily.sh - Ejecución programada del pipeline de Cuy para cron en Linux

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR" || exit 1

LOG_FILE="$BASE_DIR/cron_log.txt"

echo "========================================================" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🚀 Iniciando pipeline autónomo programado..." >> "$LOG_FILE"
echo "========================================================" >> "$LOG_FILE"

# Ejecutar el script usando el entorno virtual de Python
"$BASE_DIR/.venv/bin/python" "$BASE_DIR/generate_and_assemble_episode.py" random kimi -a cuy >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🏁 Pipeline finalizado con código de salida: $EXIT_CODE" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
