#!/bin/bash
# ==============================================================================
# OCTOPY QUIZ PROCUREMENT - Script de Limpieza de Historial MQTT y Dispositivos
# ==============================================================================
# 1. Purgar los mensajes retenidos (retained) en Mosquitto MQTT
# 2. Llamar a la API del backend para limpiar la memoria de GameEngine (si está activo)
# ==============================================================================

BROKER_HOST="${MQTT_BROKER:-127.0.0.1}"
BROKER_PORT="${MQTT_PORT:-1883}"
MQTT_USER="${MQTT_USER:-OctopyPB}"
MQTT_PASS="${MQTT_PASSWORD:-Octopy2025.}"

echo "=========================================================="
echo "🧹 Purgando historial y tópicos retenidos en Mosquitto..."
echo "Broker: $BROKER_HOST:$BROKER_PORT"
echo "=========================================================="

# Limpiar cajas OCTY-01 a OCTY-20 y BOT-01 a BOT-20
for i in $(seq -f "%02g" 1 20); do
    mosquitto_pub -h "$BROKER_HOST" -p "$BROKER_PORT" -u "$MQTT_USER" -P "$MQTT_PASS" -t "octopy/quiz/box/OCTY-$i/status" -r -n 2>/dev/null
    mosquitto_pub -h "$BROKER_HOST" -p "$BROKER_PORT" -u "$MQTT_USER" -P "$MQTT_PASS" -t "octopy/quiz/box/OCTY-$i/answer" -r -n 2>/dev/null
    mosquitto_pub -h "$BROKER_HOST" -p "$BROKER_PORT" -u "$MQTT_USER" -P "$MQTT_PASS" -t "octopy/quiz/box/BOT-$i/status" -r -n 2>/dev/null
    mosquitto_pub -h "$BROKER_HOST" -p "$BROKER_PORT" -u "$MQTT_USER" -P "$MQTT_PASS" -t "octopy/quiz/box/BOT-$i/answer" -r -n 2>/dev/null
    mosquitto_pub -h "$BROKER_HOST" -p "$BROKER_PORT" -u "$MQTT_USER" -P "$MQTT_PASS" -t "quiz/device/OCTY-$i/status" -r -n 2>/dev/null
    mosquitto_pub -h "$BROKER_HOST" -p "$BROKER_PORT" -u "$MQTT_USER" -P "$MQTT_PASS" -t "quiz/device/BOT-$i/status" -r -n 2>/dev/null
done

# Limpiar broadcast retenido si hubiese
mosquitto_pub -h "$BROKER_HOST" -p "$BROKER_PORT" -u "$MQTT_USER" -P "$MQTT_PASS" -t "octopy/quiz/broadcast" -r -n 2>/dev/null
mosquitto_pub -h "$BROKER_HOST" -p "$BROKER_PORT" -u "$MQTT_USER" -P "$MQTT_PASS" -t "quiz/game/state" -r -n 2>/dev/null

echo "✅ Mensajes retenidos purgados de Mosquitto."

# Si el backend FastAPI está activo, invocar limpieza en memoria
if curl -s -f -o /dev/null "http://127.0.0.1:8000/api/settings"; then
    echo "🔄 Conectando con Backend FastAPI (http://127.0.0.1:8000)..."
    RESPONSE=$(curl -s -X POST "http://127.0.0.1:8000/api/devices/clear" -H "Content-Type: application/json" -d '{"only_offline": false}')
    echo "✅ Memoria del backend limpiada: $RESPONSE"
else
    echo "ℹ️  Backend no está corriendo en http://127.0.0.1:8000 (se limpiará automáticamente al arrancar)."
fi

echo "=========================================================="
echo "✨ Historial completamente limpio. Las botoneras físicas"
echo "   pueden volver a encenderse o re-anunciarse limpiamente."
echo "=========================================================="
