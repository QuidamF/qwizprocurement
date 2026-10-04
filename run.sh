#!/bin/bash
# Script de inicio para Quiz Procurement (Fase 1)
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Creando entorno virtual e instalando dependencias..."
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
fi

echo "Iniciando servidor Quiz en http://localhost:8000 ..."
./venv/bin/uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
