/*
============================================================
 OCTOPY QUIZ PREMIUM
 ESP32 DevKit V1 - Firmware V2 MQTT
============================================================

 HARDWARE
 -----------------------------------------------------------
 A           GPIO 18
 B           GPIO 19
 C           GPIO 21
 D           GPIO 22

 WS2812B     GPIO 23
 STATUS LED  GPIO 25

============================================================
 MQTT TOPICS
============================================================

 Broadcast:
   octopy/quiz/broadcast

 Game state:
   octopy/quiz/game/state

 Individual:
   octopy/quiz/box/OCTY-XX/command
   octopy/quiz/box/OCTY-XX/answer
   octopy/quiz/box/OCTY-XX/status

============================================================
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include <Preferences.h>

// ============================================================
// CONFIGURACIÓN WIFI
// ============================================================

const char* WIFI_SSID     = "OctopyPB";
const char* WIFI_PASSWORD = "Octopy2025.";

// ============================================================
// CONFIGURACIÓN MQTT
// ============================================================

const char* MQTT_SERVER = "10.2.20.253";
const uint16_t MQTT_PORT = 1883;

const char* MQTT_USER = "OctopyPB";
const char* MQTT_PASSWORD = "Octopy2025.";

// ============================================================
// PINES
// ============================================================

#define PIN_BUTTON_A 18
#define PIN_BUTTON_B 19
#define PIN_BUTTON_C 21
#define PIN_BUTTON_D 22

#define PIN_WS2812 23
#define PIN_STATUS_LED 25

// ============================================================
// WS2812B
// ============================================================

// Cambiar según la longitud real de la tira
#define NUM_LEDS 36

#define RGB_BRIGHTNESS 80

Adafruit_NeoPixel strip(
  NUM_LEDS,
  PIN_WS2812,
  NEO_GRB + NEO_KHZ800
);

// ============================================================
// PREFERENCES
// ============================================================

Preferences preferences;

// ============================================================
// BOX ID
// ============================================================

// Valor inicial si todavía no existe configuración
String boxID = "OCTY-01";

// ============================================================
// MQTT TOPICS
// ============================================================

String topicCommand;
String topicAnswer;
String topicStatus;

const char* topicBroadcast =
  "octopy/quiz/broadcast";

const char* topicGameState =
  "octopy/quiz/game/state";

// ============================================================
// WIFI / MQTT
// ============================================================

WiFiClient wifiClient;

PubSubClient mqtt(wifiClient);

// ============================================================
// ESTADO DEL JUEGO
// ============================================================

bool gameActive = false;
bool answerLocked = false;

int currentQuestion = -1;

unsigned long questionStartedAt = 0;

unsigned long lastButtonTime = 0;

const unsigned long DEBOUNCE_MS = 50;

// ============================================================
// TEMPORIZADORES
// ============================================================

unsigned long lastWiFiAttempt = 0;
unsigned long lastMQTTAttempt = 0;
unsigned long lastHeartbeat = 0;

const unsigned long WIFI_RECONNECT_MS = 5000;
const unsigned long MQTT_RECONNECT_MS = 5000;
const unsigned long HEARTBEAT_MS = 10000;

// ============================================================
// BOTONES
// ============================================================

struct Button {

  uint8_t pin;
  char answer;
  bool lastState;
};

Button buttons[4] = {

  {PIN_BUTTON_A, 'A', HIGH},
  {PIN_BUTTON_B, 'B', HIGH},
  {PIN_BUTTON_C, 'C', HIGH},
  {PIN_BUTTON_D, 'D', HIGH}
};

// ============================================================
// ESTADO LED
// ============================================================

bool statusLedState = false;

// ============================================================
// GENERAR EVENT ID
// ============================================================

String generateEventID(char answer) {

  uint64_t chipID = ESP.getEfuseMac();

  String id = boxID;

  id += "-";
  id += String(currentQuestion);

  id += "-";
  id += String(answer);

  id += "-";
  id += String((uint32_t)(chipID & 0xFFFFFFFF));

  id += "-";
  id += String(millis());

  return id;
}

// ============================================================
// RGB
// ============================================================

void clearRGB() {
  strip.clear();
  strip.show();
}

void setRGB(
  uint8_t r,
  uint8_t g,
  uint8_t b
) {

  // Apagar y limpiar completamente antes de pintar para que no se queden colores pegados
  strip.clear();
  strip.show();
  delay(10);

  if (r > 0 || g > 0 || b > 0) {
    for (
      uint16_t i = 0;
      i < NUM_LEDS;
      i++
    ) {

      strip.setPixelColor(
        i,
        strip.Color(r, g, b)
      );
    }

    strip.show();
  }
}

// ============================================================
// RGB INDIVIDUAL
// ============================================================

void setPixelRGB(
  uint16_t index,
  uint8_t r,
  uint8_t g,
  uint8_t b
) {

  if (index >= NUM_LEDS)
    return;

  strip.setPixelColor(
    index,
    strip.Color(r, g, b)
  );
}

// ============================================================
// CARGAR BOX ID
// ============================================================

void loadBoxID() {

  preferences.begin(
    "octopy",
    true
  );

  String storedID =
    preferences.getString(
      "box_id",
      ""
    );

  preferences.end();

  if (
    storedID.length() > 0
  ) {

    boxID = storedID;
  }

  Serial.print(
    "BOX ID: "
  );

  Serial.println(
    boxID
  );
}

// ============================================================
// GUARDAR BOX ID
// ============================================================

void saveBoxID(
  const String& newID
) {

  preferences.begin(
    "octopy",
    false
  );

  preferences.putString(
    "box_id",
    newID
  );

  preferences.end();

  boxID = newID;

  setupMQTTTopics();

  Serial.print(
    "Nuevo BOX ID: "
  );

  Serial.println(
    boxID
  );
}

// ============================================================
// CONFIGURAR TOPICS
// ============================================================

void setupMQTTTopics() {

  topicCommand =
    "octopy/quiz/box/" +
    boxID +
    "/command";

  topicAnswer =
    "octopy/quiz/box/" +
    boxID +
    "/answer";

  topicStatus =
    "octopy/quiz/box/" +
    boxID +
    "/status";
}

// ============================================================
// STATUS MQTT
// ============================================================

void publishStatus(
  const char* status
) {

  if (!mqtt.connected())
    return;

  JsonDocument doc;

  doc["type"] = "STATUS";
  doc["box"] = boxID;
  doc["status"] = status;
  doc["question"] = currentQuestion;

  doc["wifi"] =
    WiFi.RSSI();

  doc["ip"] =
    WiFi.localIP().toString();

  doc["chip_id"] =
    String(
      (uint32_t)(ESP.getEfuseMac() & 0xFFFFFFFF)
    );

  doc["mac"] =
    WiFi.macAddress();

  doc["uptime"] =
    millis() / 1000;

  String payload;

  serializeJson(
    doc,
    payload
  );

  mqtt.publish(
    topicStatus.c_str(),
    payload.c_str(),
    true
  );
}

// ============================================================
// ENVIAR HELLO
// ============================================================

void publishHello() {

  if (!mqtt.connected())
    return;

  JsonDocument doc;

  doc["type"] = "HELLO";
  doc["box"] = boxID;

  doc["firmware"] =
    "OCTOPY-QUIZ-V2";

  doc["chip_id"] =
    String(
      (uint32_t)(ESP.getEfuseMac() & 0xFFFFFFFF)
    );

  doc["free_heap"] =
    ESP.getFreeHeap();

  doc["wifi"] =
    WiFi.RSSI();

  String payload;

  serializeJson(
    doc,
    payload
  );

  mqtt.publish(
    topicStatus.c_str(),
    payload.c_str(),
    true
  );
}

// ============================================================
// MQTT CALLBACK
// ============================================================

void mqttCallback(
  char* topic,
  byte* payload,
  unsigned int length
) {

  String message;

  for (
    unsigned int i = 0;
    i < length;
    i++
  ) {

    message +=
      (char)payload[i];
  }

  Serial.println();
  Serial.print(
    "MQTT <- "
  );

  Serial.println(
    message
  );

  JsonDocument doc;

  DeserializationError error =
    deserializeJson(
      doc,
      message
    );

  if (error) {

    Serial.println(
      "ERROR: JSON invalido"
    );

    return;
  }

  const char* cmd =
    doc["cmd"];

  if (!cmd)
    return;

  // ==========================================================
  // SET BOX ID
  // ==========================================================

  if (
    strcmp(
      cmd,
      "SET_BOX_ID"
    ) == 0
  ) {

    const char* newID =
      doc["box"];

    if (
      newID &&
      strlen(newID) > 0
    ) {

      saveBoxID(
        String(newID)
      );

      publishStatus(
        "BOX_ID_CHANGED"
      );
    }

    return;
  }

  // ==========================================================
  // START
  // ==========================================================

  if (
    strcmp(
      cmd,
      "START"
    ) == 0
  ) {

    if (
      !doc["question"].is<int>()
    ) {

      Serial.println(
        "START sin question"
      );

      return;
    }

    currentQuestion =
      doc["question"].as<int>();

    gameActive = true;

    answerLocked = false;

    questionStartedAt =
      millis();

    setRGB(
      0,
      0,
      120
    );

    publishStatus(
      "QUESTION_ACTIVE"
    );

    Serial.print(
      "Pregunta activa: "
    );

    Serial.println(
      currentQuestion
    );

    return;
  }

  // ==========================================================
  // RESET
  // ==========================================================

  if (
    strcmp(
      cmd,
      "RESET"
    ) == 0
  ) {

    gameActive = false;

    answerLocked = false;

    currentQuestion = -1;

    questionStartedAt = 0;

    setRGB(
      0,
      0,
      0
    );

    publishStatus(
      "RESET"
    );

    return;
  }

  // ==========================================================
  // WAITING
  // ==========================================================

  if (
    strcmp(
      cmd,
      "WAITING"
    ) == 0
  ) {

    gameActive = false;

    answerLocked = false;

    currentQuestion = -1;

    setRGB(
      0,
      0,
      50
    );

    publishStatus(
      "WAITING"
    );

    return;
  }

  // ==========================================================
  // ANSWER LOCKED
  // ==========================================================

  if (
    strcmp(
      cmd,
      "ANSWER_LOCKED"
    ) == 0
  ) {

    answerLocked = true;

    return;
  }

  // ==========================================================
  // CORRECT
  // ==========================================================

  if (
    strcmp(
      cmd,
      "CORRECT"
    ) == 0
  ) {

    const char* target =
      doc["box"];

    if (
      target &&
      boxID == String(target)
    ) {

      setRGB(
        0,
        180,
        0
      );

      publishStatus(
        "CORRECT"
      );
    }

    gameActive = false;

    return;
  }

  // ==========================================================
  // WRONG
  // ==========================================================

  if (
    strcmp(
      cmd,
      "WRONG"
    ) == 0
  ) {

    const char* target =
      doc["box"];

    if (
      target &&
      boxID == String(target)
    ) {

      setRGB(
        180,
        0,
        0
      );

      publishStatus(
        "WRONG"
      );
    }

    gameActive = false;

    return;
  }

  // ==========================================================
  // ALL ANSWERS CLOSED
  // ==========================================================

  if (
    strcmp(
      cmd,
      "QUESTION_END"
    ) == 0
  ) {

    gameActive = false;

    answerLocked = true;

    setRGB(
      100,
      0,
      100
    );

    publishStatus(
      "QUESTION_END"
    );

    return;
  }

  // ==========================================================
  // CLEAR / OFF
  // ==========================================================

  if (
    strcmp(
      cmd,
      "CLEAR"
    ) == 0 ||
    strcmp(
      cmd,
      "OFF"
    ) == 0
  ) {

    clearRGB();
    return;
  }
}

// ============================================================
// WIFI
// ============================================================

void startWiFi() {

  Serial.println();
  Serial.println(
    "Conectando WiFi..."
  );

  WiFi.mode(
    WIFI_STA
  );

  WiFi.setHostname(
    boxID.c_str()
  );

  WiFi.begin(
    WIFI_SSID,
    WIFI_PASSWORD
  );
}

// ------------------------------------------------------------
// TRADUCTOR DE CODIGOS DE ERROR MQTT
// ------------------------------------------------------------

const char* getMqttStateName(int state) {
  switch (state) {
    case -4: return "TIMEOUT (El servidor no responde a tiempo. Revisa IP/puerto)";
    case -3: return "CONEXION PERDIDA";
    case -2: return "CONEXION FALLIDA (No se alcanza el Broker Mosquitto)";
    case -1: return "DESCONECTADO";
    case 0:  return "CONECTADO OK";
    case 1:  return "VERSION DE PROTOCOLO INCORRECTA";
    case 2:  return "CLIENT ID RECHAZADO";
    case 3:  return "BROKER NO DISPONIBLE";
    case 4:  return "CREDENCIALES INCORRECTAS (Usuario o Password malos)";
    case 5:  return "NO AUTORIZADO";
    default: return "ERROR DESCONOCIDO";
  }
}

// ============================================================
// WIFI LOOP
// ============================================================

bool wifiWasConnected = false;

void handleWiFi() {

  if (
    WiFi.status() ==
    WL_CONNECTED
  ) {

    if (!wifiWasConnected) {
      wifiWasConnected = true;
      Serial.println("\n==================================================");
      Serial.println("  [OK] ¡WIFI CONECTADO EXITOSAMENTE!");
      Serial.print("  - Dispositivo ID: "); Serial.println(boxID);
      Serial.print("  - Dirección IP:   "); Serial.println(WiFi.localIP());
      Serial.print("  - Máscara de red: "); Serial.println(WiFi.subnetMask());
      Serial.print("  - Gateway IP:     "); Serial.println(WiFi.gatewayIP());
      Serial.print("  - Potencia RSSI:  "); Serial.print(WiFi.RSSI()); Serial.println(" dBm");
      Serial.println("==================================================");
    }
    return;
  }

  wifiWasConnected = false;

  unsigned long now =
    millis();

  if (
    now -
    lastWiFiAttempt <
    WIFI_RECONNECT_MS
  ) {

    return;
  }

  lastWiFiAttempt =
    now;

  Serial.println(
    "Intentando WiFi..."
  );

  startWiFi();
}

// ============================================================
// MQTT CONNECT
// ============================================================

bool connectMQTT() {

  if (
    WiFi.status() !=
    WL_CONNECTED
  ) {

    return false;
  }

  String clientID =
    boxID;

  clientID += "-";

  clientID +=
    String(
      (uint32_t)
      (ESP.getEfuseMac() & 0xFFFFFFFF),
      HEX
    );

  Serial.println("\n--------------------------------------------------");
  Serial.print("Conectando MQTT como ");
  Serial.println(clientID);
  Serial.printf("  - Broker:  %s:%d\n", MQTT_SERVER, MQTT_PORT);
  if (strlen(MQTT_USER) > 0) {
    Serial.printf("  - Usuario: %s (con contraseña)\n", MQTT_USER);
  } else {
    Serial.println("  - Modo:    Anónimo (sin credenciales)");
  }

  bool connected;

  if (
    strlen(MQTT_USER) > 0
  ) {

    connected =
      mqtt.connect(
        clientID.c_str(),
        MQTT_USER,
        MQTT_PASSWORD,

        topicStatus.c_str(),
        1,
        true,

        "{\"type\":\"STATUS\",\"status\":\"OFFLINE\"}"
      );

  } else {

    connected =
      mqtt.connect(
        clientID.c_str(),

        topicStatus.c_str(),
        1,
        true,

        "{\"type\":\"STATUS\",\"status\":\"OFFLINE\"}"
      );
  }

  if (!connected) {

    int st = mqtt.state();
    Serial.printf("  [ERROR] Falló la conexión MQTT (rc = %d): %s\n", st, getMqttStateName(st));
    Serial.println("  Reintentando en el siguiente ciclo...");
    Serial.println("--------------------------------------------------");

    return false;
  }

  Serial.println("==================================================");
  Serial.println("  [OK] ¡MQTT CONECTADO EXITOSAMENTE!");
  Serial.printf("  - Dispositivo: %s\n", boxID.c_str());
  Serial.printf("  - Suscripciones activas:\n");
  Serial.printf("      * %s\n", topicCommand.c_str());
  Serial.printf("      * %s\n", topicBroadcast);
  Serial.printf("      * %s\n", topicGameState);
  Serial.println("==================================================");

  // ----------------------------------------------------------
  // Suscripciones
  // ----------------------------------------------------------

  mqtt.subscribe(
    topicCommand.c_str(),
    1
  );

  mqtt.subscribe(
    topicBroadcast,
    1
  );

  mqtt.subscribe(
    topicGameState,
    1
  );

  publishHello();

  publishStatus(
    "ONLINE"
  );

  // Indicar conexión al broker con Azul en el Pin 23
  setRGB(
    0,
    0,
    150
  );

  delay(
    1000
  );

  // Apagar tira y quedar a la espera de comandos de la aplicación
  clearRGB();

  return true;
}

// ============================================================
// MQTT LOOP
// ============================================================

void handleMQTT() {

  if (
    WiFi.status() !=
    WL_CONNECTED
  ) {

    return;
  }

  if (
    mqtt.connected()
  ) {

    mqtt.loop();

    return;
  }

  unsigned long now =
    millis();

  if (
    now -
    lastMQTTAttempt <
    MQTT_RECONNECT_MS
  ) {

    return;
  }

  lastMQTTAttempt =
    now;

  connectMQTT();
}

// ============================================================
// ENVIAR RESPUESTA
// ============================================================

void sendAnswer(
  char answer
) {

  if (
    !mqtt.connected()
  ) {

    Serial.println(
      "MQTT desconectado"
    );

    return;
  }

  JsonDocument doc;

  doc["type"] =
    "ANSWER";

  doc["box"] =
    boxID;

  doc["question"] =
    currentQuestion;

  doc["answer"] =
    String(answer);

  doc["timestamp"] =
    millis();

  doc["reaction_ms"] =
    millis() -
    questionStartedAt;

  doc["event_id"] =
    generateEventID(answer);

  String payload;

  serializeJson(
    doc,
    payload
  );

  bool result =
    mqtt.publish(
      topicAnswer.c_str(),
      payload.c_str(),
      false
    );

  if (result) {

    Serial.print(
      "RESPUESTA -> "
    );

    Serial.println(
      payload
    );

  } else {

    Serial.println(
      "ERROR MQTT ANSWER"
    );
  }
}

// ============================================================
// LEER BOTONES
// ============================================================

void handleButtons() {

  if (!gameActive)
    return;

  if (answerLocked)
    return;

  unsigned long now =
    millis();

  if (
    now -
    lastButtonTime <
    DEBOUNCE_MS
  ) {

    return;
  }

  for (
    int i = 0;
    i < 4;
    i++
  ) {

    bool currentState =
      digitalRead(
        buttons[i].pin
      );

    // --------------------------------------------------------
    // Detectar flanco HIGH -> LOW
    // --------------------------------------------------------

    if (
      buttons[i].lastState == HIGH &&
      currentState == LOW
    ) {

      lastButtonTime =
        now;

      char answer =
        buttons[i].answer;

      Serial.print(
        "BOTON PRESIONADO: "
      );

      Serial.println(
        answer
      );

      // Bloqueo INMEDIATO
      answerLocked = true;

      // Feedback local
      setRGB(
        120,
        80,
        0
      );

      // Enviar respuesta
      sendAnswer(
        answer
      );

      break;
    }

    buttons[i].lastState =
      currentState;
  }
}

// ============================================================
// HEARTBEAT
// ============================================================

void handleHeartbeat() {

  if (
    millis() -
    lastHeartbeat <
    HEARTBEAT_MS
  ) {

    return;
  }

  lastHeartbeat =
    millis();

  if (
    mqtt.connected()
  ) {

    publishStatus(
      "ONLINE"
    );
  }
}

// ============================================================
// STATUS LED
// ============================================================

void handleStatusLED() {

  static unsigned long lastBlink =
    0;

  static bool state =
    false;

  if (
    WiFi.status() !=
    WL_CONNECTED
  ) {

    if (
      millis() -
      lastBlink >
      250
    ) {

      lastBlink =
        millis();

      state =
        !state;

      digitalWrite(
        PIN_STATUS_LED,
        state
      );
    }

    return;
  }

  if (
    !mqtt.connected()
  ) {

    if (
      millis() -
      lastBlink >
      500
    ) {

      lastBlink =
        millis();

      state =
        !state;

      digitalWrite(
        PIN_STATUS_LED,
        state
      );
    }

    return;
  }

  // Todo correcto
  digitalWrite(
    PIN_STATUS_LED,
    HIGH
  );
}

// ============================================================
// SETUP
// ============================================================

void setup() {

  Serial.begin(
    115200
  );

  delay(300);

  Serial.println();
  Serial.println(
    "================================"
  );

  Serial.println(
    "   OCTOPY QUIZ PREMIUM V2"
  );

  Serial.println(
    "   ESP32 + MQTT"
  );

  Serial.println(
    "================================"
  );

  // ----------------------------------------------------------
  // Cargar configuración
  // ----------------------------------------------------------

  loadBoxID();

  setupMQTTTopics();

  // ----------------------------------------------------------
  // GPIO
  // ----------------------------------------------------------

  pinMode(
    PIN_BUTTON_A,
    INPUT_PULLUP
  );

  pinMode(
    PIN_BUTTON_B,
    INPUT_PULLUP
  );

  pinMode(
    PIN_BUTTON_C,
    INPUT_PULLUP
  );

  pinMode(
    PIN_BUTTON_D,
    INPUT_PULLUP
  );

  pinMode(
    PIN_STATUS_LED,
    OUTPUT
  );

  digitalWrite(
    PIN_STATUS_LED,
    LOW
  );

  // ----------------------------------------------------------
  // Inicializar estados botones
  // ----------------------------------------------------------

  for (
    int i = 0;
    i < 4;
    i++
  ) {

    buttons[i].lastState =
      digitalRead(
        buttons[i].pin
      );
  }

  // ----------------------------------------------------------
  // WS2812B
  // ----------------------------------------------------------

  strip.begin();

  strip.setBrightness(
    RGB_BRIGHTNESS
  );

  strip.clear();

  strip.show();

  // ----------------------------------------------------------
  // MQTT
  // ----------------------------------------------------------

  mqtt.setServer(
    MQTT_SERVER,
    MQTT_PORT
  );

  mqtt.setCallback(
    mqttCallback
  );

  // Permitir JSON MQTT relativamente grande
  mqtt.setBufferSize(
    1024
  );

  // ----------------------------------------------------------
  // WiFi
  // ----------------------------------------------------------

  startWiFi();

  // ----------------------------------------------------------
  // Encendido / Boot: Verde en Pin 23 y después apagar
  // ----------------------------------------------------------

  setRGB(
    0,
    180,
    0
  );

  delay(
    800
  );

  clearRGB();

  Serial.println();
  Serial.println(
    "Sistema iniciado."
  );
}

// ============================================================
// LOOP PRINCIPAL
// ============================================================

void loop() {

  // WiFi
  handleWiFi();

  // MQTT
  handleMQTT();

  // Botones
  handleButtons();

  // Heartbeat
  handleHeartbeat();

  // LED de estado
  handleStatusLED();

  // Pequeña cesión al sistema
  delay(1);
}