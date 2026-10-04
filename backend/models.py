from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from enum import Enum
import time

class GameStateEnum(str, Enum):
    IDLE = "IDLE"
    LOBBY = "LOBBY"
    QUESTION_READY = "QUESTION_READY"
    ACTIVE = "ACTIVE"
    TIMEOUT = "TIMEOUT"
    RESULT = "RESULT"
    FINISHED = "FINISHED"

class Question(BaseModel):
    id: int
    level: str = "Básico"
    text: str
    options: Dict[str, str]
    correct_answer: str
    time_limit: int = 15

class QuestionPublic(BaseModel):
    id: int
    level: str
    text: str
    options: Dict[str, str]
    time_limit: int

class DeviceStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    WAITING = "WAITING"
    ANSWERED = "ANSWERED"
    LOCKED = "LOCKED"

class ConnectionType(str, Enum):
    WEB = "WEB"
    MQTT = "MQTT"

class Device(BaseModel):
    device_id: str
    name: str
    status: DeviceStatus = DeviceStatus.ONLINE
    connection_type: ConnectionType = ConnectionType.WEB
    hardware_id: Optional[str] = None # MAC or Chip ID
    chip_id: Optional[str] = None
    ip_address: Optional[str] = None
    wifi_rssi: Optional[int] = None # dBm
    uptime: Optional[int] = None
    firmware: Optional[str] = "OCTOPY-QUIZ-V2"
    last_seen: Optional[float] = None
    score: int = 0
    current_answer: Optional[str] = None
    answer_time: Optional[float] = None
    answer_order: Optional[int] = None
    reaction_ms: Optional[int] = None
    is_correct: Optional[bool] = None

class AnswerSubmission(BaseModel):
    device_id: str
    button: str
    sequence: Optional[int] = None
    reaction_ms: Optional[int] = None
    event_id: Optional[str] = None

class DeviceRegistration(BaseModel):
    hardware_id: str
    device_id: Optional[str] = None
    name: Optional[str] = None
    firmware: Optional[str] = "OCTOPY-QUIZ-V2"
    chip_id: Optional[str] = None
    ip_address: Optional[str] = None
    wifi_rssi: Optional[int] = None
    connection_type: ConnectionType = ConnectionType.MQTT

class ModeratorAction(BaseModel):
    action: str
    question_id: Optional[int] = None
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    time_limit: Optional[int] = None
