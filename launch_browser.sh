#!/usr/bin/env bash
# launch_browser.sh - Inicia el navegador con Remote Debugging Port (CDP) activado

PORT=9222
CDP_URL="http://127.0.0.1:${PORT}/json/version"

# 1. Comprobar si ya está activo el puerto CDP
if curl -s "$CDP_URL" > /dev/null 2>&1; then
    echo "✅ El puerto de depuración remota ya está activo en http://127.0.0.1:${PORT}"
    exit 0
fi

# 2. Detectar binario del navegador
BROWSER_BIN=""
if [ -x "/snap/bin/brave" ]; then
    BROWSER_BIN="/snap/bin/brave"
elif command -v google-chrome &>/dev/null; then
    BROWSER_BIN=$(command -v google-chrome)
elif command -v google-chrome-stable &>/dev/null; then
    BROWSER_BIN=$(command -v google-chrome-stable)
elif command -v brave-browser &>/dev/null; then
    BROWSER_BIN=$(command -v brave-browser)
elif command -v chromium &>/dev/null; then
    BROWSER_BIN=$(command -v chromium)
fi

if [ -z "$BROWSER_BIN" ]; then
    echo "❌ No se encontró ningún navegador basado en Chromium (Brave, Chrome, Chromium)."
    exit 1
fi

echo "🔍 Navegador detectado: $BROWSER_BIN"

# 3. Comprobar si ya hay una instancia corriendo sin el puerto
RUNNING_PIDS=$(pgrep -f "$(basename "$BROWSER_BIN")" 2>/dev/null)
if [ -n "$RUNNING_PIDS" ]; then
    echo "⚠️  Se detectaron instancias de $(basename "$BROWSER_BIN") en ejecución."
    echo "   Para conectar con tu sesión activa de Flow (y tus créditos), el navegador debe"
    echo "   iniciarse con el flag --remote-debugging-port=${PORT}."
    echo ""
    read -p "¿Deseas cerrar el navegador actual y reiniciarlo con depuración remota? (s/N): " RESP
    if [[ "$RESP" =~ ^[sSyY]$ ]]; then
        echo "Cerrando navegador..."
        pkill -f "$(basename "$BROWSER_BIN")"
        sleep 2
    else
        echo "Operación cancelada. Cierra tu navegador manualmente y vuelve a ejecutar este script."
        exit 1
    fi
fi

# 4. Lanzar navegador con puerto CDP
echo "🚀 Lanzando $BROWSER_BIN con --remote-debugging-port=${PORT}..."
nohup "$BROWSER_BIN" --remote-debugging-port=${PORT} --restore-last-session > /dev/null 2>&1 &
disown

# 5. Esperar a que el puerto responda
echo -n "Esperando conexión con el navegador"
for i in {1..15}; do
    if curl -s "$CDP_URL" > /dev/null 2>&1; then
        echo " ✅ ¡Conectado con éxito!"
        echo "Navegador listo en http://127.0.0.1:${PORT}"
        exit 0
    fi
    echo -n "."
    sleep 1
done

echo ""
echo "⚠️  El navegador se inició, pero el puerto ${PORT} aún no responde."
echo "Comprueba abriendo http://127.0.0.1:${PORT}/json/version en otra terminal."

