#!/bin/bash
# ==============================================================================
# Script Kiosk para Raspberry Pi (Zero 2 W / 3 / 4 / 5)
# Lanza Chromium en modo pantalla completa sin bordes hacia /screen
# ==============================================================================

# 1. Espera de arranque inicial solicitada (20 segundos)
echo "[Quiz Kiosk] Esperando 20 segundos para estabilizar el sistema y servicios..."
sleep 20

# 2. Verificación de salud: Asegurar que FastAPI ya está respondiendo
TARGET_URL="http://localhost:8000/screen"
echo "[Quiz Kiosk] Verificando disponibilidad de $TARGET_URL ..."
MAX_ATTEMPTS=30
ATTEMPT=0

while ! curl -s --head --fail "$TARGET_URL" > /dev/null; do
    ATTEMPT=$((ATTEMPT + 1))
    if [ $ATTEMPT -ge $MAX_ATTEMPTS ]; then
        echo "[Quiz Kiosk] Advertencia: Se alcanzó el límite de intentos. Intentando abrir de todos modos..."
        break
    fi
    echo "[Quiz Kiosk] Backend aún no disponible (intento $ATTEMPT/$MAX_ATTEMPTS). Reintentando en 2s..."
    sleep 2
done

echo "[Quiz Kiosk] Backend en línea. Preparando entorno de visualización..."

# 3. Variables de entorno de display gráfico
export DISPLAY="${DISPLAY:-:0}"
if [ -f "$HOME/.Xauthority" ]; then
    export XAUTHORITY="$HOME/.Xauthority"
fi

# 4. Desactivar reposo de pantalla / screensaver si xset está disponible (X11)
if command -v xset > /dev/null 2>&1; then
    xset s noblank || true
    xset s off || true
    xset -dpms || true
fi

# 5. Localizar binario de Chromium (chromium-browser en Raspberry Pi OS o chromium)
CHROMIUM_BIN=$(command -v chromium-browser || command -v chromium)

if [ -z "$CHROMIUM_BIN" ]; then
    echo "[Error] No se encontró el binario de Chromium en el sistema."
    echo "Instálalo con: sudo apt install -y chromium-browser"
    exit 1
fi

# 6. Evitar el cuadro de diálogo molesto de 'Restaurar pestañas tras cierre inesperado'
PREFS_DIR="$HOME/.config/chromium/Default"
if [ -d "$PREFS_DIR" ]; then
    sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' "$PREFS_DIR/Preferences" 2>/dev/null || true
    sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PREFS_DIR/Preferences" 2>/dev/null || true
fi

# 7. Ejecutar Chromium en modo Kiosko optimizado para hardware embebido (RPi Zero 2 W)
exec "$CHROMIUM_BIN" \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-session-crashed-bubble \
    --disable-features=TranslateUI \
    --disable-translate \
    --disk-cache-size=10485760 \
    --media-cache-size=10485760 \
    --check-for-update-interval=31536000 \
    --autoplay-policy=no-user-gesture-required \
    --disable-pinch \
    --overscroll-history-navigation=0 \
    "$TARGET_URL"
