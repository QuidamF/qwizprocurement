#!/usr/bin/env bash
# ====================================================================
# Ejecutar Modulo de Prueba Simple (Servidor Web + Puente MQTT)
# ====================================================================
cd "$(dirname "$0")/.."
echo "Iniciando Servidor de Prueba en http://localhost:8080 ..."
./venv/bin/python test/server.py
