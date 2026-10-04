#!/usr/bin/env python3
"""
====================================================================
OCTOPY - SERVIDOR DE PRUEBA SIMPLE (BACKEND + MQTT BRIDGE)
====================================================================
Sirve el frontend en http://0.0.0.0:8080 y hace de puente con Mosquitto:
- Topico de envio al ESP32: octopy/test/led
- Topico de recepcion del ESP32: octopy/test/status
"""

import os
import json
import asyncio
import logging
from typing import Set, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
import uvicorn
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TestServer")

# Configuracion MQTT
MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1")  # Mosquitto local o 10.2.20.253
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "OctopyPB")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "Octopy2025.")

TOPIC_COMMAND = "octopy/test/led"
TOPIC_STATUS = "octopy/test/status"

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_HTML = os.path.join(CURRENT_DIR, "index.html")

# Gestor de conexiones WebSocket (Frontend)
class WSManager:
    def __init__(self):
        self.connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.add(ws)

    def disconnect(self, ws: WebSocket):
        self.connections.discard(ws)

    async def broadcast(self, message: Dict[str, Any]):
        msg_str = json.dumps(message)
        for ws in list(self.connections):
            try:
                await ws.send_text(msg_str)
            except Exception:
                self.disconnect(ws)

ws_manager = WSManager()

# Cliente MQTT
mqtt_client: mqtt.Client = None
loop: asyncio.AbstractEventLoop = None

def on_mqtt_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info(f"Conectado exitosamente a Mosquitto ({MQTT_BROKER}:{MQTT_PORT})")
        client.subscribe(TOPIC_STATUS, qos=1)
        logger.info(f"Suscrito a: {TOPIC_STATUS}")
    else:
        logger.error(f"Fallo de conexión MQTT (rc={rc})")

def on_mqtt_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)
        logger.info(f"[MQTT RX] {msg.topic}: {payload_str}")

        # Retransmitir al Frontend via WebSocket
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast(data), loop)
    except Exception as e:
        logger.error(f"Error procesando mensaje MQTT: {e}")

def publish_mqtt(payload: Dict[str, Any]):
    if mqtt_client:
        msg = json.dumps(payload, ensure_ascii=False)
        mqtt_client.publish(TOPIC_COMMAND, msg, qos=1)
        logger.info(f"[MQTT TX] {TOPIC_COMMAND}: {msg}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mqtt_client, loop
    loop = asyncio.get_running_loop()
    try:
        mqtt_client = mqtt.Client(client_id="octopy-test-server", protocol=mqtt.MQTTv311)
        if MQTT_USER:
            mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_message = on_mqtt_message

        logger.info(f"Conectando a broker MQTT en {MQTT_BROKER}:{MQTT_PORT}...")
        mqtt_client.connect_async(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
    except Exception as e:
        logger.error(f"No se pudo iniciar MQTT: {e}")
    yield
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

app = FastAPI(title="Octopy LED Test Server", lifespan=lifespan)

@app.get("/")
async def get_index():
    return FileResponse(INDEX_HTML)

@app.post("/api/command")
async def post_command(cmd_data: Dict[str, Any]):
    publish_mqtt(cmd_data)
    return {"status": "ok", "sent": cmd_data}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
                publish_mqtt(data)
            except Exception as e:
                logger.error(f"Error procesando WS: {e}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

if __name__ == "__main__":
    logger.info("Iniciando Servidor de Prueba en http://0.0.0.0:8080")
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=False)
