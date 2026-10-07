import os
import json
import logging
from typing import Dict, Set, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from backend.game_engine import GameEngine
from backend.mqtt_service import MQTTService
from backend.models import AnswerSubmission, ModeratorAction, DeviceRegistration, ConnectionType, DeviceStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("quiz.app")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "frontend", "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "frontend", "templates")

# Instantiate Engine & MQTT Service
engine = GameEngine(questions_path=os.path.join(BASE_DIR, "backend", "questions.json"))
mqtt_service = MQTTService(broker_host="127.0.0.1", broker_port=1883)
engine.set_mqtt_service(mqtt_service)

# Wire MQTT inbound events to GameEngine
mqtt_service.set_callbacks(
    on_answer=engine.submit_answer,
    on_status=engine.handle_mqtt_status
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start MQTT client
    logger.info("Starting MQTT Service...")
    await mqtt_service.start()
    yield
    # Shutdown: Stop MQTT client
    logger.info("Stopping MQTT Service...")
    mqtt_service.stop()

app = FastAPI(title="Quiz Procurement API & Game Engine", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.screen_connections: Set[WebSocket] = set()
        self.moderator_connections: Set[WebSocket] = set()
        self.devices_connections: Set[WebSocket] = set()
        self.buzzer_connections: Dict[str, Set[WebSocket]] = {}

    async def connect_screen(self, ws: WebSocket):
        await ws.accept()
        self.screen_connections.add(ws)

    def disconnect_screen(self, ws: WebSocket):
        self.screen_connections.discard(ws)

    async def connect_moderator(self, ws: WebSocket):
        await ws.accept()
        self.moderator_connections.add(ws)

    def disconnect_moderator(self, ws: WebSocket):
        self.moderator_connections.discard(ws)

    async def connect_devices_manager(self, ws: WebSocket):
        await ws.accept()
        self.devices_connections.add(ws)

    def disconnect_devices_manager(self, ws: WebSocket):
        self.devices_connections.discard(ws)

    async def connect_buzzer(self, device_id: str, ws: WebSocket):
        await ws.accept()
        if device_id not in self.buzzer_connections:
            self.buzzer_connections[device_id] = set()
        self.buzzer_connections[device_id].add(ws)

    def disconnect_buzzer(self, device_id: str, ws: WebSocket):
        if device_id in self.buzzer_connections:
            self.buzzer_connections[device_id].discard(ws)
            if not self.buzzer_connections[device_id]:
                del self.buzzer_connections[device_id]

    async def broadcast_to_group(self, target_group: str, message: Dict[str, Any]):
        msg_str = json.dumps(message, ensure_ascii=False)
        dead_conns = []

        if target_group in ["all", "screen"]:
            for ws in list(self.screen_connections):
                try:
                    await ws.send_text(msg_str)
                except Exception:
                    dead_conns.append(("screen", ws, None))

        if target_group in ["all", "moderator"]:
            for ws in list(self.moderator_connections):
                try:
                    await ws.send_text(msg_str)
                except Exception:
                    dead_conns.append(("moderator", ws, None))

        if target_group in ["all", "devices"]:
            for ws in list(self.devices_connections):
                try:
                    await ws.send_text(msg_str)
                except Exception:
                    dead_conns.append(("devices", ws, None))

        if target_group in ["all", "buzzers"]:
            for dev_id, conns in list(self.buzzer_connections.items()):
                for ws in list(conns):
                    try:
                        await ws.send_text(msg_str)
                    except Exception:
                        dead_conns.append(("buzzer", ws, dev_id))

        if target_group.startswith("device_"):
            dev_id = target_group.replace("device_", "")
            if dev_id in self.buzzer_connections:
                for ws in list(self.buzzer_connections[dev_id]):
                    try:
                        await ws.send_text(msg_str)
                    except Exception:
                        dead_conns.append(("buzzer", ws, dev_id))

        for ctype, ws, dev_id in dead_conns:
            if ctype == "screen":
                self.disconnect_screen(ws)
            elif ctype == "moderator":
                self.disconnect_moderator(ws)
            elif ctype == "devices":
                self.disconnect_devices_manager(ws)
            elif ctype == "buzzer" and dev_id:
                self.disconnect_buzzer(dev_id, ws)

manager = ConnectionManager()

async def engine_broadcast_hook(target_group: str, message: Dict[str, Any]):
    await manager.broadcast_to_group(target_group, message)

engine.set_broadcast_callback(engine_broadcast_hook)

# ----------------- HTML Route Handlers -----------------

@app.api_route("/", methods=["GET", "HEAD"], response_class=FileResponse)
async def index_page():
    return FileResponse(os.path.join(TEMPLATES_DIR, "index.html"))

@app.api_route("/screen", methods=["GET", "HEAD"], response_class=FileResponse)
async def screen_page():
    return FileResponse(os.path.join(TEMPLATES_DIR, "screen.html"))

@app.api_route("/moderator", methods=["GET", "HEAD"], response_class=FileResponse)
async def moderator_page():
    return FileResponse(os.path.join(TEMPLATES_DIR, "moderator.html"))

@app.get("/moderator/backup", response_class=FileResponse)
async def moderator_backup_page():
    return FileResponse(os.path.join(TEMPLATES_DIR, "moderator_backup.html"))

@app.get("/buzzer", response_class=FileResponse)
async def buzzer_page():
    return FileResponse(os.path.join(TEMPLATES_DIR, "buzzer.html"))

@app.get("/multi-buzzer", response_class=FileResponse)
async def multi_buzzer_page():
    return FileResponse(os.path.join(TEMPLATES_DIR, "multi_buzzer.html"))

@app.get("/devices", response_class=FileResponse)
async def devices_manager_page():
    return FileResponse(os.path.join(TEMPLATES_DIR, "devices.html"))

# ----------------- REST API -----------------

@app.get("/api/state")
async def get_state():
    return engine.get_moderator_snapshot()

@app.get("/api/questions")
async def get_questions():
    return [q.model_dump() for q in engine.questions]

@app.get("/api/devices")
async def get_devices():
    return engine.get_devices_list()

class DeviceUpdateRequest(BaseModel):
    name: Optional[str] = None
    hardware_id: Optional[str] = None

@app.post("/api/devices/{device_id}/update")
async def update_device_endpoint(device_id: str, body: DeviceUpdateRequest):
    await engine.update_device_info(device_id, name=body.name, hardware_id=body.hardware_id)
    return {"status": "ok"}

@app.post("/api/devices/{device_id}/identify")
async def identify_device_endpoint(device_id: str):
    await engine.identify_device(device_id)
    return {"status": "ok", "message": f"Identify command sent to {device_id}"}

@app.delete("/api/devices/{device_id}")
@app.post("/api/devices/{device_id}/delete")
async def delete_device_endpoint(device_id: str):
    removed = await engine.remove_device(device_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    return {"status": "ok", "removed": device_id}

class ClearDevicesRequest(BaseModel):
    only_offline: bool = False

@app.post("/api/devices/clear")
async def clear_devices_endpoint(body: Optional[ClearDevicesRequest] = None):
    only_offline = body.only_offline if body else False
    count = await engine.clear_devices(only_offline=only_offline)
    return {"status": "ok", "cleared_count": count, "only_offline": only_offline}

class VirtualBuzzersRequest(BaseModel):
    allow: bool

@app.post("/api/settings/virtual-buzzers")
async def toggle_virtual_buzzers_endpoint(body: VirtualBuzzersRequest):
    await engine.set_allow_virtual_buzzers(body.allow)
    return {"status": "ok", "allow_virtual_buzzers": engine.allow_virtual_buzzers}

@app.get("/api/settings")
async def get_settings_endpoint():
    return {
        "allow_virtual_buzzers": engine.allow_virtual_buzzers,
        "mqtt_connected": mqtt_service.is_connected,
        "total_devices": len(engine.devices)
    }

@app.post("/api/devices/register")
async def register_device_api(reg: DeviceRegistration):
    dev = await engine.register_mqtt_device(reg)
    return {"status": "ok", "device": dev.model_dump()}

@app.post("/api/answer")
async def submit_answer(sub: AnswerSubmission):
    res = await engine.submit_answer(sub)
    if res["status"] != "accepted":
        raise HTTPException(status_code=400, detail=res.get("reason", "Submission rejected"))
    return res

@app.post("/api/moderator/action")
async def moderator_action(act: ModeratorAction):
    action = act.action.lower()
    if action == "start_lobby":
        await engine.start_lobby()
    elif action in ["start_game", "start_trivia"]:
        await engine.start_game(auto_start=True)
    elif action == "select_question":
        if act.question_id is None:
            raise HTTPException(status_code=400, detail="question_id required")
        ok = await engine.select_question(act.question_id, auto_start=True)
        if not ok:
            raise HTTPException(status_code=404, detail="Question not found")
    elif action == "start_question":
        await engine.start_question()
    elif action == "close_question":
        await engine.close_question()
    elif action == "show_result":
        await engine.show_result()
    elif action == "next_question":
        await engine.next_question(auto_start=True)
    elif action == "reset_game":
        await engine.reset_game(reset_scores=True)
    elif action == "identify":
        if act.device_id:
            await engine.identify_device(act.device_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {act.action}")
    return {"status": "ok", "state": engine.state.value}

# ----------------- WebSockets -----------------

@app.websocket("/ws/devices")
async def ws_devices_endpoint(websocket: WebSocket):
    """WebSocket channel for Device Manager live dashboard."""
    await manager.connect_devices_manager(websocket)
    try:
        # Send initial full device list
        await websocket.send_text(json.dumps({
            "event": "DEVICES_SNAPSHOT",
            "devices": engine.get_devices_list(),
            "mqtt_connected": mqtt_service.is_connected,
            "allow_virtual_buzzers": engine.allow_virtual_buzzers
        }, ensure_ascii=False))

        while True:
            text = await websocket.receive_text()
            try:
                payload = json.loads(text)
                cmd = payload.get("command")
                if cmd == "identify":
                    dev_id = payload.get("device_id")
                    if dev_id:
                        await engine.identify_device(dev_id)
                elif cmd == "update":
                    dev_id = payload.get("device_id")
                    name = payload.get("name")
                    hw_id = payload.get("hardware_id")
                    if dev_id:
                        await engine.update_device_info(dev_id, name=name, hardware_id=hw_id)
                elif cmd == "remove_device":
                    dev_id = payload.get("device_id")
                    if dev_id:
                        await engine.remove_device(dev_id)
                elif cmd == "clear_devices":
                    only_off = payload.get("only_offline", False)
                    await engine.clear_devices(only_offline=only_off)
                elif cmd == "toggle_virtual_buzzers":
                    allow = payload.get("allow")
                    if allow is None:
                        allow = not engine.allow_virtual_buzzers
                    await engine.set_allow_virtual_buzzers(allow)
            except Exception as e:
                logger.error(f"Devices WS error: {e}")
    except WebSocketDisconnect:
        manager.disconnect_devices_manager(websocket)

@app.websocket("/ws/screen")
async def ws_screen_endpoint(websocket: WebSocket):
    await manager.connect_screen(websocket)
    try:
        await websocket.send_text(json.dumps({
            "event": "SNAPSHOT",
            "snapshot": engine.get_screen_snapshot()
        }, ensure_ascii=False))

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_screen(websocket)

@app.websocket("/ws/moderator")
async def ws_moderator_endpoint(websocket: WebSocket):
    await manager.connect_moderator(websocket)
    try:
        await websocket.send_text(json.dumps({
            "event": "SNAPSHOT",
            "snapshot": engine.get_moderator_snapshot()
        }, ensure_ascii=False))

        while True:
            text = await websocket.receive_text()
            try:
                payload = json.loads(text)
                action = payload.get("action")
                if action:
                    act = ModeratorAction(**payload)
                    await moderator_action(act)
            except Exception as e:
                logger.error(f"Moderator WS error: {e}")
    except WebSocketDisconnect:
        manager.disconnect_moderator(websocket)

@app.websocket("/ws/buzzer/{device_id}")
async def ws_buzzer_endpoint(websocket: WebSocket, device_id: str):
    device_id = engine.normalize_device_id(device_id)

    # 0. Check if virtual buzzers are enabled
    if not engine.allow_virtual_buzzers:
        logger.warning(f"Rechazada conexión de botonera web {device_id}: botoneras virtuales deshabilitadas.")
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "event": "ERROR",
            "message": "Las botoneras virtuales están deshabilitadas por el moderador. Solo se admiten botoneras físicas ESP32 vía MQTT."
        }, ensure_ascii=False))
        await websocket.close(code=1008)
        return

    # 1. Obtain real client IP
    client_ip = websocket.client.host if websocket.client else "127.0.0.1"
    forwarded = websocket.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif websocket.headers.get("x-real-ip"):
        client_ip = websocket.headers.get("x-real-ip").strip()

    # 2. IP Validation:
    # Reject duplicate web buzzers from the same IP (only allow 1 web device per IP address)
    for existing_id, dev in engine.devices.items():
        if (dev.connection_type == ConnectionType.WEB 
            and dev.status == DeviceStatus.ONLINE 
            and dev.ip_address == client_ip 
            and existing_id != device_id):
            logger.warning(f"Rechazado dispositivo web duplicado desde la misma IP {client_ip}: intentó {device_id}, ya activo como {existing_id}")
            await websocket.accept()
            await websocket.send_text(json.dumps({
                "event": "ERROR",
                "message": f"Conexión rechazada: Ya existe el equipo '{dev.name}' ({existing_id}) activo desde esta dirección IP ({client_ip}). Cada equipo debe conectarse desde un dispositivo o IP diferente."
            }, ensure_ascii=False))
            await websocket.close(code=1008)
            return

    # 3. Connect & Register with its real IP
    await manager.connect_buzzer(device_id, websocket)
    engine.register_device(device_id, connection_type=ConnectionType.WEB, ip_address=client_ip)

    # 4. Broadcast state change in REAL TIME to moderator, screen, and devices
    await engine.broadcast_state_change()

    try:
        await websocket.send_text(json.dumps({
            "event": "SNAPSHOT",
            "snapshot": engine.get_device_snapshot(device_id)
        }, ensure_ascii=False))

        while True:
            text = await websocket.receive_text()
            try:
                payload = json.loads(text)
                button = payload.get("button")
                if button:
                    sub = AnswerSubmission(device_id=device_id, button=button)
                    await engine.submit_answer(sub)
            except Exception as e:
                logger.error(f"Buzzer WS error for {device_id}: {e}")
    except WebSocketDisconnect:
        manager.disconnect_buzzer(device_id, websocket)
        engine.disconnect_device(device_id)
        await engine.broadcast_state_change()
