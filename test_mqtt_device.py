#!/usr/bin/env python3
"""
Simulador idéntico al firmware arduino/botonera.ino (ESP32 DevKit V1 - Firmware V2 MQTT).
Prueba exactamente los tópicos y comandos de la botonera real:
- Tópicos de estado: octopy/quiz/box/OCTY-01/status
- Tópicos de respuesta: octopy/quiz/box/OCTY-01/answer
- Tópicos de comando: octopy/quiz/box/OCTY-01/command y octopy/quiz/broadcast
"""

import sys
import time
import json
import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883
BOX_ID = "OCTY-01"
CHIP_ID = "24718392"

current_question = 1
game_active = False
answer_locked = False
question_started_at = 0

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"\n[ESP32 {BOX_ID}] Conectado a Mosquitto ({BROKER}:{PORT})")
    
    # 1. Suscribirse a los tópicos exactamente como botonera.ino
    topic_command = f"octopy/quiz/box/{BOX_ID}/command"
    topic_broadcast = "octopy/quiz/broadcast"
    topic_game_state = "octopy/quiz/game/state"
    
    client.subscribe(topic_command, qos=1)
    client.subscribe(topic_broadcast, qos=1)
    client.subscribe(topic_game_state, qos=1)
    
    # 2. Publicar HELLO
    hello_doc = {
        "type": "HELLO",
        "box": BOX_ID,
        "firmware": "OCTOPY-QUIZ-V2",
        "chip_id": CHIP_ID,
        "free_heap": 241580,
        "wifi": -52
    }
    client.publish(f"octopy/quiz/box/{BOX_ID}/status", json.dumps(hello_doc), qos=1, retain=True)
    print(f"[ESP32 {BOX_ID}] Enviado HELLO a 'octopy/quiz/box/{BOX_ID}/status'")

    # 3. Publicar STATUS ONLINE
    status_doc = {
        "type": "STATUS",
        "box": BOX_ID,
        "status": "ONLINE",
        "question": current_question,
        "wifi": -52,
        "ip": "192.168.1.105",
        "uptime": 14
    }
    client.publish(f"octopy/quiz/box/{BOX_ID}/status", json.dumps(status_doc), qos=1, retain=True)

def on_message(client, userdata, msg):
    global game_active, answer_locked, current_question, question_started_at
    topic = msg.topic
    try:
        doc = json.loads(msg.payload.decode('utf-8'))
    except Exception:
        return
    
    cmd = doc.get("cmd")
    if not cmd:
        return
    
    if cmd == "START":
        current_question = doc.get("question", 1)
        game_active = True
        answer_locked = False
        question_started_at = time.time() * 1000
        print(f"\n💡 [WS2812B AZUL (0,0,120)]: ¡Pregunta #{current_question} ACTIVA! Botones desbloqueados.")
    
    elif cmd == "QUESTION_END":
        game_active = False
        answer_locked = True
        print(f"\n💡 [WS2812B MORADO (100,0,100)]: Tiempo cerrado / Fin de pregunta. Botones bloqueados.")
        
    elif cmd == "CORRECT":
        target = doc.get("box")
        if target == BOX_ID:
            game_active = False
            print(f"\n🎉 [WS2812B VERDE (0,180,0)]: ¡RESPUESTA CORRECTA! (+{doc.get('points', 0)} pts)")
            
    elif cmd == "WRONG":
        target = doc.get("box")
        if target == BOX_ID:
            game_active = False
            print(f"\n❌ [WS2812B ROJO (180,0,0)]: RESPUESTA INCORRECTA.")
            
    elif cmd == "WAITING":
        game_active = False
        answer_locked = False
        print(f"\n💡 [WS2812B AZUL TENUE (0,0,50)]: En espera...")
        
    elif cmd == "RESET":
        game_active = False
        answer_locked = False
        current_question = -1
        print(f"\n💡 [WS2812B APAGADO (0,0,0)]: Sistema Reiniciado.")

def send_button(client, button_char):
    global answer_locked
    answer_char = button_char.upper()
    answer_locked = True
    print(f"\n💡 [WS2812B ÁMBAR (120,80,0)]: Bloqueo local inmediato por pulsación '{answer_char}'.")
    
    reaction_ms = int((time.time() * 1000) - question_started_at) if question_started_at else 950
    doc = {
        "type": "ANSWER",
        "box": BOX_ID,
        "question": current_question,
        "answer": answer_char,
        "timestamp": int(time.time() * 1000),
        "reaction_ms": max(10, reaction_ms),
        "event_id": f"{BOX_ID}-{current_question}-{answer_char}-{CHIP_ID}-{int(time.time())}"
    }
    topic = f"octopy/quiz/box/{BOX_ID}/answer"
    client.publish(topic, json.dumps(doc), qos=1)
    print(f"🔘 [MQTT TX] Enviado a {topic}: {json.dumps(doc)}")

def main():
    print("=" * 65)
    print(f" SIMULADOR EXACTO DE 'arduino/botonera.ino' (Box: {BOX_ID})")
    print("=" * 65)

    try:
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"{BOX_ID}-{CHIP_ID}"
        )
    except Exception:
        client = mqtt.Client(client_id=f"{BOX_ID}-{CHIP_ID}")

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start()
    except Exception as e:
        print(f"Error conectando a broker: {e}")
        return

    if len(sys.argv) > 1:
        time.sleep(1)
        send_button(client, sys.argv[1])
        time.sleep(2)
        client.loop_stop()
        return

    print("\nEscribe una opción (A, B, C, D) para presionar el botón físico:")
    print("Escribe 'exit' para salir.")
    try:
        while True:
            cmd = input().strip().upper()
            if cmd == "EXIT":
                break
            elif cmd in ["A", "B", "C", "D"]:
                send_button(client, cmd)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
