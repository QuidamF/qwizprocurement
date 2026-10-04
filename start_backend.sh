#!/bin/bash
# ==============================================================================
# Script de Arranque del Backend FastAPI para PM2
# Verifica o crea el entorno virtual automáticamente si no existe
# ==============================================================================

cd "$(dirname "$0")"

# 1. Asegurar que el directorio de logs exista
mkdir -p logs

# 2. Si no existe venv o uvicorn, crearlo e instalar dependencias
if [ ! -f "venv/bin/uvicorn" ]; then
    echo "[Backend] Entorno virtual no encontrado o incompleto en $(pwd)/venv."
    echo "[Backend] Creando entorno virtual e instalando dependencias..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
fi

echo "[Backend] Iniciando Uvicorn en http://0.0.0.0:8000 ..."
# Usar exec para que PM2 monitoree directamente el proceso de Uvicorn
exec ./venv/bin/python3 -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
