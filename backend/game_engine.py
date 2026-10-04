import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Set, Callable, Any
from backend.models import (
    GameStateEnum,
    Question,
    QuestionPublic,
    Device,
    DeviceStatus,
    ConnectionType,
    AnswerSubmission,
    DeviceRegistration
)

logger = logging.getLogger("quiz.engine")

def resolve_hardware_id(ip_address: Optional[str]) -> Optional[str]:
    """Tries to resolve real physical MAC address from Linux ARP table for local network devices."""
    if not ip_address or ip_address in ("127.0.0.1", "localhost", "::1"):
        return None
    try:
        with open("/proc/net/arp", "r") as f:
            for line in f.readlines()[1:]:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == ip_address:
                    mac = parts[3].upper()
                    if mac != "00:00:00:00:00:00":
                        return mac
    except Exception:
        pass
    return None

class GameEngine:
    def __init__(self, questions_path: str = "backend/questions.json"):
        self.questions_path = questions_path
        self.questions: List[Question] = []
        self.load_questions()

        self.state: GameStateEnum = GameStateEnum.IDLE
        self.current_question_index: int = -1
        self.current_question: Optional[Question] = None
        
        # Elapsed timer
        self.question_start_time: Optional[float] = None
        self.elapsed_seconds: float = 0.0
        self.timer_ticker_task: Optional[asyncio.Task] = None
        
        # Real connected devices dictionary (MQTT and Web from unique IPs)
        self.devices: Dict[str, Device] = {}

        # Responses for the current question
        self.current_answers: List[Dict[str, Any]] = []

        # Broadcast callback (WebSockets)
        self.broadcast_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None
        
        # MQTT Service reference
        self.mqtt_service = None

    def load_questions(self):
        try:
            with open(self.questions_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.questions = [Question(**item) for item in data]
            logger.info(f"Loaded {len(self.questions)} questions from {self.questions_path}")
        except Exception as e:
            logger.error(f"Error loading questions: {e}")
            self.questions = []

    def set_broadcast_callback(self, cb: Callable[[str, Dict[str, Any]], Any]):
        self.broadcast_callback = cb

    def set_mqtt_service(self, mqtt_srv):
        self.mqtt_service = mqtt_srv

    async def broadcast(self, target_group: str, message: Dict[str, Any]):
        if self.broadcast_callback:
            await self.broadcast_callback(target_group, message)

    def normalize_device_id(self, device_id: str) -> str:
        """Normalizes BOT-XX to OCTY-XX or accepts OCTY-XX."""
        d = device_id.upper().strip()
        if d.startswith("BOT-"):
            return d.replace("BOT-", "OCTY-")
        return d

    # ---------------- Device Registration & Telemetry ----------------

    def register_device(self, device_id: str, name: Optional[str] = None, connection_type: ConnectionType = ConnectionType.WEB, ip_address: Optional[str] = None) -> Device:
        device_id = self.normalize_device_id(device_id)
        hw_id = resolve_hardware_id(ip_address)
        if not hw_id:
            if connection_type == ConnectionType.WEB:
                hw_id = f"NET-{ip_address}" if ip_address else "WEB-CLIENT"
            else:
                hw_id = f"ESP32-{device_id}"

        if device_id not in self.devices:
            self.devices[device_id] = Device(
                device_id=device_id,
                name=name or f"Equipo {device_id}",
                status=DeviceStatus.ONLINE,
                connection_type=connection_type,
                hardware_id=hw_id,
                ip_address=ip_address,
                last_seen=time.time()
            )
        else:
            self.devices[device_id].status = DeviceStatus.ONLINE
            self.devices[device_id].connection_type = connection_type
            self.devices[device_id].last_seen = time.time()
            if ip_address:
                self.devices[device_id].ip_address = ip_address
            if not self.devices[device_id].hardware_id or self.devices[device_id].hardware_id.startswith("ESP32-"):
                if hw_id:
                    self.devices[device_id].hardware_id = hw_id
            if name:
                self.devices[device_id].name = name
        return self.devices[device_id]

    async def register_mqtt_device(self, reg: DeviceRegistration) -> Device:
        dev_id = self.normalize_device_id(reg.device_id or f"OCTY-{len(self.devices) + 1:02d}")
        dev = self.register_device(
            device_id=dev_id,
            name=reg.name or f"Equipo {dev_id}",
            connection_type=reg.connection_type,
            ip_address=reg.ip_address
        )
        dev.hardware_id = reg.hardware_id or resolve_hardware_id(reg.ip_address)
        dev.chip_id = reg.chip_id
        dev.wifi_rssi = reg.wifi_rssi
        dev.firmware = reg.firmware
        await self.broadcast_state_change()
        return dev

    async def handle_mqtt_status(self, box_id: str, data: Dict[str, Any]):
        """Processes HELLO and STATUS payloads from arduino/botonera.ino."""
        box_id = self.normalize_device_id(box_id)
        msg_type = data.get("type", "STATUS")
        
        dev = self.devices.get(box_id)
        if not dev:
            dev = self.register_device(box_id, connection_type=ConnectionType.MQTT)

        dev.connection_type = ConnectionType.MQTT
        dev.last_seen = time.time()

        if "wifi" in data:
            dev.wifi_rssi = data.get("wifi")
        if "ip" in data:
            dev.ip_address = data.get("ip")
        if "uptime" in data:
            dev.uptime = data.get("uptime")
            
        # Hardware / Physical ID detection
        if "chip_id" in data:
            dev.chip_id = str(data.get("chip_id"))
            dev.hardware_id = f"CHIP-{dev.chip_id}"
        elif "mac" in data:
            dev.hardware_id = str(data.get("mac")).upper()
        elif "hardware_id" in data:
            dev.hardware_id = str(data.get("hardware_id")).upper()
        elif not dev.hardware_id or dev.hardware_id.startswith("ESP32-"):
            resolved_mac = resolve_hardware_id(dev.ip_address)
            if resolved_mac:
                dev.hardware_id = resolved_mac
            elif not dev.hardware_id:
                dev.hardware_id = f"ESP32-{box_id}"

        if "firmware" in data:
            dev.firmware = data.get("firmware")

        raw_status = data.get("status", "")
        if raw_status == "OFFLINE":
            dev.status = DeviceStatus.OFFLINE
        else:
            dev.status = DeviceStatus.ONLINE

        logger.info(f"Updated status for {box_id} ({msg_type}): HW={dev.hardware_id}, IP={dev.ip_address}, WiFi={dev.wifi_rssi}dBm, Status={dev.status}")

        # Broadcast state change in REAL TIME to all listeners (moderator, screen, devices)
        await self.broadcast_state_change()

    async def update_device_info(self, device_id: str, name: Optional[str] = None, new_box_id: Optional[str] = None, hardware_id: Optional[str] = None):
        """Allows renaming or commanding ESP32 to change its box ID."""
        device_id = self.normalize_device_id(device_id)
        if device_id in self.devices:
            dev = self.devices[device_id]
            if name:
                dev.name = name.strip()
            if hardware_id:
                dev.hardware_id = hardware_id.strip()

            # If user wants to reassign boxID on the physical ESP32
            if new_box_id and new_box_id.upper() != device_id:
                new_id = self.normalize_device_id(new_box_id)
                if self.mqtt_service:
                    self.mqtt_service.publish_set_box_id(device_id, new_id)
                # Migrate in devices dict
                self.devices[new_id] = dev
                dev.device_id = new_id
                del self.devices[device_id]

            dev.last_seen = time.time()
            
            # Broadcast state change in REAL TIME to all listeners (moderator, screen, devices, buzzers)
            await self.broadcast_state_change()

    async def identify_device(self, device_id: str):
        """Commands the ESP32 or web buzzer to flash its LEDs."""
        device_id = self.normalize_device_id(device_id)
        if device_id in self.devices:
            if self.mqtt_service:
                self.mqtt_service.publish_identify(device_id)
            
            await self.broadcast(f"device_{device_id}", {
                "event": "IDENTIFY",
                "device_id": device_id
            })

    def disconnect_device(self, device_id: str):
        device_id = self.normalize_device_id(device_id)
        if device_id in self.devices:
            self.devices[device_id].status = DeviceStatus.OFFLINE
            self.devices[device_id].last_seen = time.time()

    # ---------------- Helper Queries ----------------

    def get_pending_devices(self) -> List[Dict[str, Any]]:
        pending = []
        for dev in self.devices.values():
            if dev.status == DeviceStatus.ONLINE and dev.current_answer is None:
                pending.append({
                    "device_id": dev.device_id,
                    "name": dev.name,
                    "status": dev.status.value,
                    "is_online": True,
                    "connection_type": dev.connection_type.value,
                    "wifi_rssi": dev.wifi_rssi,
                    "ip_address": dev.ip_address
                })
        return pending

    def get_devices_list(self) -> List[Dict[str, Any]]:
        return [dev.model_dump() for dev in self.devices.values()]

    # ---------------- State Machine Transitions ----------------

    async def start_lobby(self):
        self.state = GameStateEnum.LOBBY
        if self.mqtt_service:
            self.mqtt_service.publish_waiting()
        await self.broadcast_state_change()

    async def select_question(self, question_id: int, auto_start: bool = True):
        for idx, q in enumerate(self.questions):
            if q.id == question_id:
                self.current_question_index = idx
                self.current_question = q
                self.current_answers = []
                self._reset_device_question_state()
                
                if auto_start:
                    self.state = GameStateEnum.ACTIVE
                    self.question_start_time = time.time()
                    self._start_elapsed_ticker()
                    if self.mqtt_service:
                        self.mqtt_service.publish_start(question_number=q.id)
                else:
                    self.state = GameStateEnum.QUESTION_READY
                    self.question_start_time = None
                    self._stop_elapsed_ticker()
                    if self.mqtt_service:
                        self.mqtt_service.publish_waiting()

                await self.broadcast_state_change()
                return True
        return False

    async def start_question(self):
        if not self.current_question:
            if self.questions:
                await self.select_question(self.questions[0].id, auto_start=True)
                return
            return

        self._reset_device_question_state()
        self.current_answers = []
        self.state = GameStateEnum.ACTIVE
        self.question_start_time = time.time()
        self._start_elapsed_ticker()
        
        if self.mqtt_service:
            self.mqtt_service.publish_start(question_number=self.current_question.id)
            
        await self.broadcast_state_change()

    def _start_elapsed_ticker(self):
        if self.timer_ticker_task and not self.timer_ticker_task.done():
            self.timer_ticker_task.cancel()
        self.timer_ticker_task = asyncio.create_task(self._run_ticker())

    def _stop_elapsed_ticker(self):
        if self.timer_ticker_task and not self.timer_ticker_task.done():
            self.timer_ticker_task.cancel()

    async def _run_ticker(self):
        try:
            while self.state == GameStateEnum.ACTIVE:
                if self.question_start_time:
                    self.elapsed_seconds = round(time.time() - self.question_start_time, 1)
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass

    async def close_question(self, reason: str = "MANUAL"):
        self._stop_elapsed_ticker()
        self.state = GameStateEnum.TIMEOUT

        for dev in self.devices.values():
            if dev.current_answer is None:
                dev.status = DeviceStatus.LOCKED

        if self.mqtt_service:
            self.mqtt_service.publish_question_end()

        await self.broadcast_state_change()

    async def show_result(self):
        if not self.current_question:
            return

        self._stop_elapsed_ticker()
        self.state = GameStateEnum.RESULT
        correct_ans = self.current_question.correct_answer.upper()

        correct_counter = 0
        for entry in self.current_answers:
            dev_id = entry["device_id"]
            dev = self.devices.get(dev_id)
            if not dev:
                continue

            if entry["answer"] == correct_ans:
                correct_counter += 1
                bonus = 50 if correct_counter == 1 else (30 if correct_counter == 2 else (10 if correct_counter == 3 else 0))
                points = 100 + bonus
                entry["is_correct"] = True
                entry["points"] = points
                dev.is_correct = True
                dev.score += points
                # Send MQTT command CORRECT to turn LEDs Green (0, 180, 0)
                if self.mqtt_service:
                    self.mqtt_service.publish_correct(dev_id, points=points)
            else:
                entry["is_correct"] = False
                entry["points"] = 0
                dev.is_correct = False
                # Send MQTT command WRONG to turn LEDs Red (180, 0, 0)
                if self.mqtt_service:
                    self.mqtt_service.publish_wrong(dev_id)

        await self.broadcast_state_change()

    async def start_game(self, auto_start: bool = True):
        """Starts the quiz game from the very first question (Question 1)."""
        if self.questions:
            await self.select_question(self.questions[0].id, auto_start=auto_start)

    async def next_question(self, auto_start: bool = True):
        if self.current_question is None or self.current_question_index < 0:
            next_idx = 0
        else:
            next_idx = self.current_question_index + 1

        if next_idx < len(self.questions):
            await self.select_question(self.questions[next_idx].id, auto_start=auto_start)
        else:
            self.state = GameStateEnum.FINISHED
            if self.mqtt_service:
                self.mqtt_service.publish_waiting()
            await self.broadcast_state_change()

    async def reset_game(self, reset_scores: bool = True):
        self._stop_elapsed_ticker()
        self.state = GameStateEnum.IDLE
        self.current_question_index = -1
        self.current_question = None
        self.current_answers = []

        # Prune inactive / offline devices on reset
        self.devices = {
            dev_id: dev for dev_id, dev in self.devices.items()
            if dev.status != DeviceStatus.OFFLINE
        }

        for dev in self.devices.values():
            dev.current_answer = None
            dev.answer_time = None
            dev.answer_order = None
            dev.reaction_ms = None
            dev.is_correct = None
            dev.status = DeviceStatus.ONLINE
            if reset_scores:
                dev.score = 0

        if self.mqtt_service:
            self.mqtt_service.publish_reset()

        await self.broadcast_state_change()

    # ---------------- Answer Ingestion (Web & botonera.ino) ----------------

    async def submit_answer(self, submission: AnswerSubmission) -> Dict[str, Any]:
        dev_id = self.normalize_device_id(submission.device_id)
        button = submission.button.strip().upper()

        if self.state != GameStateEnum.ACTIVE:
            return {"status": "rejected", "reason": "QUESTION_NOT_ACTIVE"}

        dev = self.devices.get(dev_id)
        if not dev:
            dev = self.register_device(dev_id, connection_type=ConnectionType.MQTT)

        if dev.current_answer is not None:
            return {"status": "rejected", "reason": "ALREADY_ANSWERED"}

        recv_time = time.time()
        order = len(self.current_answers) + 1
        
        dev.current_answer = button
        dev.answer_time = recv_time
        dev.answer_order = order
        dev.reaction_ms = submission.reaction_ms
        dev.status = DeviceStatus.ANSWERED
        dev.last_seen = recv_time

        ans_record = {
            "device_id": dev_id,
            "device_name": dev.name,
            "answer": button,
            "timestamp": recv_time,
            "order": order,
            "reaction_ms": submission.reaction_ms,
            "is_correct": None,
            "points": 0
        }
        self.current_answers.append(ans_record)

        # Notify buzzer via WebSocket
        await self.broadcast(f"device_{dev_id}", {
            "event": "ANSWER_ACCEPTED",
            "device_id": dev_id,
            "answer": button,
            "order": order
        })

        pending = self.get_pending_devices()

        # Notify moderator
        await self.broadcast("moderator", {
            "event": "ANSWER_RECEIVED",
            "submission": ans_record,
            "total_answers": len(self.current_answers),
            "pending_devices": pending,
            "pending_count": len(pending)
        })

        # Notify screen
        await self.broadcast("screen", {
            "event": "ANSWER_COUNT_UPDATE",
            "total_answers": len(self.current_answers),
            "pending_devices": pending,
            "pending_count": len(pending),
            "device_id": dev_id,
            "device_name": dev.name
        })

        # Update Device Manager
        await self.broadcast("devices", {
            "event": "DEVICE_ANSWERED",
            "device_id": dev_id,
            "order": order
        })

        return {"status": "accepted", "order": order}

    def _reset_device_question_state(self):
        for dev in self.devices.values():
            dev.current_answer = None
            dev.answer_time = None
            dev.answer_order = None
            dev.reaction_ms = None
            dev.is_correct = None
            if dev.status != DeviceStatus.OFFLINE:
                dev.status = DeviceStatus.ONLINE

    # ---------------- Snapshots ----------------

    def get_public_question(self) -> Optional[QuestionPublic]:
        if not self.current_question:
            return None
        return QuestionPublic(
            id=self.current_question.id,
            level=self.current_question.level,
            text=self.current_question.text,
            options=self.current_question.options,
            time_limit=15
        )

    def get_screen_snapshot(self) -> Dict[str, Any]:
        pub_q = self.get_public_question()
        pending = self.get_pending_devices()
        total_online = len([d for d in self.devices.values() if d.status == DeviceStatus.ONLINE])
        return {
            "state": self.state.value,
            "question": pub_q.model_dump() if pub_q else None,
            "current_question_index": (self.current_question_index + 1) if self.current_question else 0,
            "total_questions": len(self.questions),
            "answer_count": len(self.current_answers),
            "pending_devices": pending,
            "pending_count": len(pending),
            "total_devices": total_online,
            "correct_answer": self.current_question.correct_answer if self.state in [GameStateEnum.RESULT, GameStateEnum.FINISHED] and self.current_question else None,
            "leaderboard": self.get_leaderboard()
        }

    def get_moderator_snapshot(self) -> Dict[str, Any]:
        pending = self.get_pending_devices()
        total_online = len([d for d in self.devices.values() if d.status == DeviceStatus.ONLINE])
        return {
            "state": self.state.value,
            "current_question": self.current_question.model_dump() if self.current_question else None,
            "current_question_index": self.current_question_index,
            "total_questions": len(self.questions),
            "questions_summary": [{"id": q.id, "level": q.level, "text": q.text, "correct_answer": q.correct_answer} for q in self.questions],
            "answers": self.current_answers,
            "pending_devices": pending,
            "pending_count": len(pending),
            "total_devices": total_online,
            "total_registered": len(self.devices),
            "devices": self.get_devices_list(),
            "leaderboard": self.get_leaderboard()
        }

    def get_device_snapshot(self, device_id: str) -> Dict[str, Any]:
        device_id = self.normalize_device_id(device_id)
        dev = self.devices.get(device_id)
        can_answer = (self.state == GameStateEnum.ACTIVE) and (dev is not None) and (dev.current_answer is None)
        return {
            "state": self.state.value,
            "device_id": device_id,
            "device_name": dev.name if dev else f"Equipo {device_id}",
            "can_answer": can_answer,
            "selected_answer": dev.current_answer if dev else None,
            "order": dev.answer_order if dev else None,
            "is_correct": dev.is_correct if (self.state in [GameStateEnum.RESULT, GameStateEnum.FINISHED] and dev) else None,
            "score": dev.score if dev else 0
        }

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        sorted_devs = sorted(self.devices.values(), key=lambda d: d.score, reverse=True)
        return [
            {
                "device_id": d.device_id,
                "name": d.name,
                "score": d.score,
                "status": d.status.value,
                "connection_type": d.connection_type.value,
                "hardware_id": d.hardware_id,
                "chip_id": d.chip_id,
                "wifi_rssi": d.wifi_rssi,
                "ip_address": d.ip_address,
                "uptime": d.uptime,
                "firmware": d.firmware,
                "last_answer": d.current_answer,
                "reaction_ms": d.reaction_ms,
                "order": d.answer_order,
                "is_correct": d.is_correct
            }
            for d in sorted_devs
        ]

    async def broadcast_state_change(self):
        await self.broadcast("screen", {
            "event": "STATE_UPDATE",
            "snapshot": self.get_screen_snapshot()
        })
        await self.broadcast("moderator", {
            "event": "STATE_UPDATE",
            "snapshot": self.get_moderator_snapshot()
        })
        await self.broadcast("devices", {
            "event": "DEVICES_SNAPSHOT",
            "devices": self.get_devices_list()
        })
        for dev_id in self.devices.keys():
            await self.broadcast(f"device_{dev_id}", {
                "event": "STATE_UPDATE",
                "snapshot": self.get_device_snapshot(dev_id)
            })
