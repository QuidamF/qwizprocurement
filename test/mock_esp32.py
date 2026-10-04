#!/usr/bin/env python3
"""
Simulador por terminal del ESP32 para el módulo de prueba.
Permite verificar la comunicación MQTT sin necesidad de tener el microcontrolador físico a la mano.
"""
import sys
import json
import time
import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883
USER = "OctopyPB"
PASS = "Octopy2025."

TOPIC_COMMAND = "octopy/test/led"
TOPIC_STATUS = "octopy/test/status"

PALETTE = [
    ("Rojo", "#DC1414"),
    ("Verde", "#14DC32"),
    ("Azul", "#1450F0"),
    ("Amarillo", "#F0C814"),
    ("Cyan", "#14DCDC"),
    ("Magenta", "#C814C8"),
    ("Naranja", "#F06414"),
    ("Blanco", "#B4B4B4"),
]
current_idx = -1

def on_connect(client, userdata, flags, rc):
    print(f"\n[MOCK ESP32] Conectado al broker MQTT ({BROKER}:{PORT})")
    client.subscribe(TOPIC_COMMAND)
    print(f"[MOCK ESP32] Suscrito a comandos: {TOPIC_COMMAND}")
    client.publish(TOPIC_STATUS, json.dumps({"event": "ONLINE", "ip": "10.2.20.99"}))

def on_message(client, userdata, msg):
    global current_idx
    try:
        data = json.loads(msg.payload.decode())
        cmd = data.get("cmd")
        print(f"\n[MOCK ESP32] <-- Comando recibido: {cmd}")
        if cmd in ("RESET", "OFF"):
            current_idx = -1
            print("  💡 [TIRA LED 36]: APAGADA (Reset)")
        elif cmd == "SET_COLOR":
            current_idx = data.get("index", -1)
            name = data.get("name", "Personalizado")
            hex_c = data.get("hex", "")
            print(f"  💡 [TIRA LED 36]: ENCENDIDA con color '{name}' ({hex_c})")
    except Exception as e:
        print("Error:", e)

def main():
    global current_idx
    client = mqtt.Client(client_id="mock-esp32-tester")
    if USER:
        client.username_pw_set(USER, PASS)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)
    client.loop_start()

    print("=======================================================")
    print("  SIMULADOR ESP32 PARA TEST DE LEDS (PIN 23)")
    print("  Presiona ENTER en esta terminal para simular la")
    print("  pulsación del botón físico y ciclar entre los 8 colores.")
    print("  Presiona Ctrl+C para salir.")
    print("=======================================================")

    try:
        while True:
            input()
            current_idx = (current_idx + 1) % len(PALETTE)
            col_name, col_hex = PALETTE[current_idx]
            print(f"\n🔘 [BOTON FISICO PRESIONADO] -> Cambiando a Color #{current_idx + 1}: {col_name} ({col_hex})")
            payload = {
                "event": "COLOR_CHANGED",
                "index": current_idx,
                "name": col_name,
                "hex": col_hex
            }
            client.publish(TOPIC_STATUS, json.dumps(payload))
    except KeyboardInterrupt:
        client.loop_stop()
        client.disconnect()
        print("\nSaliendo...")

if __name__ == "__main__":
    main()
