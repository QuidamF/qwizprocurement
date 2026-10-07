import asyncio
import json
import logging
import time
from typing import Optional, Dict, Any, Callable
import paho.mqtt.client as mqtt
from backend.models import AnswerSubmission, DeviceRegistration, ConnectionType

logger = logging.getLogger("quiz.mqtt")

class MQTTService:
    def __init__(self, broker_host: str = "127.0.0.1", broker_port: int = 1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client: Optional[mqtt.Client] = None
        self.is_connected = False
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Callbacks hooked to GameEngine
        self.on_answer_callback: Optional[Callable[[AnswerSubmission], Any]] = None
        self.on_status_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None

    def set_callbacks(self, on_answer, on_status):
        self.on_answer_callback = on_answer
        self.on_status_callback = on_status

    async def start(self):
        """Initializes and runs the MQTT client loop."""
        self.main_loop = asyncio.get_running_loop()
        
        try:
            self.client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id="QuizServer_OctopyEngine",
                protocol=mqtt.MQTTv311
            )
        except Exception:
            self.client = mqtt.Client(client_id="QuizServer_OctopyEngine")

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        try:
            logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}...")
            self.client.connect_async(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Failed to start MQTT client: {e}")

    def stop(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        logger.info(f"Connected to MQTT Broker successfully with code {rc}")
        self.is_connected = True

        # Subscriptions matching arduino/botonera.ino topics:
        # 1. Box status & HELLO: octopy/quiz/box/+/status
        client.subscribe("octopy/quiz/box/+/status")
        # 2. Box answer: octopy/quiz/box/+/answer
        client.subscribe("octopy/quiz/box/+/answer")

        # Also support legacy quiz/ topics
        client.subscribe("quiz/device/register")
        client.subscribe("quiz/device/+/announce")
        client.subscribe("quiz/device/+/answer")
        client.subscribe("quiz/device/+/status")

        # Announce server online on octopy broadcast
        self.publish("octopy/quiz/broadcast", {"type": "SERVER_STATUS", "status": "ONLINE", "timestamp": time.time()})

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        logger.warning(f"Disconnected from MQTT Broker (code {rc})")
        self.is_connected = False

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        if not msg.payload or len(msg.payload) == 0:
            logger.info(f"MQTT RX [{topic}]: Mensaje retenido purgado (vacío)")
            return
        payload_str = msg.payload.decode("utf-8", errors="ignore")
        if not payload_str.strip():
            logger.info(f"MQTT RX [{topic}]: Payload vacío, ignorado")
            return
        logger.info(f"MQTT RX [{topic}]: {payload_str}")

        try:
            data = json.loads(payload_str)
        except Exception:
            data = {"raw": payload_str}

        if self.main_loop and self.main_loop.is_running():
            asyncio.run_coroutine_threadsafe(self._process_message(topic, data), self.main_loop)

    async def _process_message(self, topic: str, data: Dict[str, Any]):
        parts = topic.split("/")

        # Format from arduino/botonera.ino:
        # Topic: octopy/quiz/box/{boxID}/answer
        if len(parts) == 5 and parts[0] == "octopy" and parts[2] == "box" and parts[4] == "answer":
            box_id = parts[3].upper()
            button = data.get("answer") or data.get("button")
            reaction_ms = data.get("reaction_ms")
            event_id = data.get("event_id")

            if button and self.on_answer_callback:
                sub = AnswerSubmission(
                    device_id=box_id,
                    button=str(button),
                    reaction_ms=reaction_ms,
                    event_id=event_id
                )
                await self.on_answer_callback(sub)

        # Topic: octopy/quiz/box/{boxID}/status (HELLO, STATUS, ONLINE, OFFLINE)
        elif len(parts) == 5 and parts[0] == "octopy" and parts[2] == "box" and parts[4] == "status":
            box_id = parts[3].upper()
            if self.on_status_callback:
                await self.on_status_callback(box_id, data)

        # Legacy quiz/device/{device_id}/answer
        elif len(parts) == 4 and parts[0] == "quiz" and parts[3] == "answer":
            device_id = parts[2].upper()
            button = data.get("button") or data.get("answer")
            if button and self.on_answer_callback:
                sub = AnswerSubmission(device_id=device_id, button=str(button))
                await self.on_answer_callback(sub)

        # Legacy quiz/device/register
        elif topic == "quiz/device/register" or (len(parts) == 4 and parts[3] == "announce"):
            box_id = (data.get("device_id") or parts[2]).upper()
            if self.on_status_callback:
                await self.on_status_callback(box_id, data)

    # ---------------- Outbound Commands to botonera.ino ----------------

    def publish(self, topic: str, payload: Any, qos: int = 1, retain: bool = False):
        if not self.client or not self.is_connected:
            return
        payload_str = json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload
        self.client.publish(topic, payload_str, qos=qos, retain=retain)

    def publish_start(self, question_number: int):
        """
        Tells all ESP32s that a question is active.
        botonera.ino turns LEDs blue (setRGB 0, 0, 120) and unlocks buttons.
        """
        payload = {"cmd": "START", "question": question_number}
        self.publish("octopy/quiz/broadcast", payload)
        self.publish("octopy/quiz/game/state", payload)
        # Also legacy
        self.publish("quiz/game/state", {"state": "ACTIVE", "question_id": question_number})

    def publish_question_end(self):
        """
        Tells all ESP32s that answering is closed.
        botonera.ino locks buttons and turns LEDs purple (setRGB 100, 0, 100).
        """
        payload = {"cmd": "QUESTION_END"}
        self.publish("octopy/quiz/broadcast", payload)
        self.publish("octopy/quiz/game/state", payload)
        # Also legacy
        self.publish("quiz/game/state", {"state": "TIMEOUT"})

    def publish_correct(self, box_id: str, points: int = 0):
        """
        botonera.ino checks if boxID == doc['box'].
        Sets LEDs green (setRGB 0, 180, 0).
        """
        box_id = box_id.upper()
        payload = {"cmd": "CORRECT", "box": box_id, "points": points}
        self.publish(f"octopy/quiz/box/{box_id}/command", payload)
        self.publish("octopy/quiz/broadcast", payload)
        # Also legacy
        self.publish(f"quiz/device/{box_id}/feedback", {"result": "correct", "led": "green", "points": points})

    def publish_wrong(self, box_id: str):
        """
        botonera.ino checks if boxID == doc['box'].
        Sets LEDs red (setRGB 180, 0, 0).
        """
        box_id = box_id.upper()
        payload = {"cmd": "WRONG", "box": box_id}
        self.publish(f"octopy/quiz/box/{box_id}/command", payload)
        self.publish("octopy/quiz/broadcast", payload)
        # Also legacy
        self.publish(f"quiz/device/{box_id}/feedback", {"result": "incorrect", "led": "red"})

    def publish_waiting(self):
        """
        botonera.ino sets LEDs to dim blue (setRGB 0, 0, 50).
        """
        payload = {"cmd": "WAITING"}
        self.publish("octopy/quiz/broadcast", payload)
        self.publish("octopy/quiz/game/state", payload)

    def publish_reset(self):
        """
        botonera.ino clears LEDs (setRGB 0, 0, 0).
        """
        payload = {"cmd": "RESET"}
        self.publish("octopy/quiz/broadcast", payload)
        self.publish("octopy/quiz/game/state", payload)

    def publish_set_box_id(self, old_box_id: str, new_box_id: str):
        """
        Commands ESP32 to save a new box_id in its NVS Preferences.
        """
        payload = {"cmd": "SET_BOX_ID", "box": new_box_id.upper()}
        self.publish(f"octopy/quiz/box/{old_box_id.upper()}/command", payload)

    def publish_identify(self, box_id: str):
        """
        Flashes the ESP32 LEDs green to physically identify it without changing game state.
        """
        box_id = box_id.upper()
        self.publish(f"octopy/quiz/box/{box_id}/command", {"cmd": "CORRECT", "box": box_id})
        if self.main_loop:
            self.main_loop.call_later(1.5, lambda: self.publish(f"octopy/quiz/box/{box_id}/command", {"cmd": "WAITING"}))

    def publish_connection_welcome(self, box_id: str):
        """
        Sends a visual welcome signal (Green flash -> Dim Blue) to the ESP32
        as soon as it connects to the network, using the preconfigured commands
        already in botonera.ino so the firmware does not need to be re-flashed.
        """
        box_id = box_id.upper()
        self.publish(f"octopy/quiz/box/{box_id}/command", {"cmd": "CORRECT", "box": box_id})
        if self.main_loop:
            self.main_loop.call_later(1.2, lambda: self.publish(f"octopy/quiz/box/{box_id}/command", {"cmd": "WAITING"}))

    def clear_retained_status(self, box_id: str):
        """
        Clears retained MQTT status messages for a device.
        In MQTT standard, publishing an empty payload with retain=True deletes the retained message.
        """
        box_id = box_id.upper()
        topics = [
            f"octopy/quiz/box/{box_id}/status",
            f"octopy/quiz/box/{box_id}/answer",
            f"quiz/device/{box_id}/status",
            f"quiz/device/{box_id}/announce"
        ]
        for t in topics:
            if self.client and self.is_connected:
                self.client.publish(t, payload="", qos=1, retain=True)
                logger.info(f"MQTT Retained topic cleared: {t}")

    def clear_all_retained_statuses(self, box_ids: Optional[list] = None):
        """
        Clears retained MQTT messages for a list of box IDs or standard range (OCTY-01 to OCTY-20).
        """
        if not box_ids:
            box_ids = [f"OCTY-{i:02d}" for i in range(1, 21)] + [f"BOT-{i:02d}" for i in range(1, 21)]
        for b_id in box_ids:
            self.clear_retained_status(b_id)
