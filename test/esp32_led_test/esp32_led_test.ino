/*
 * ====================================================================
 * OCTOPY - MODULO DE PRUEBA ESP32 (LED WS2812B + BOTONES + MQTT)
 * ====================================================================
 * - Pin WS2812: GPIO 23 (36 LEDs)
 * - Pin Status LED: GPIO 25
 * - Botones: GPIO 18 (A), 19 (B), 21 (C), 22 (D)
 *
 * COMPORTAMIENTO:
 * 1. Al encender: Verde en Pin 23 (800ms) y se apaga.
 * 2. Al conectar al broker MQTT: Azul en Pin 23 (1000ms) y se apaga.
 * 3. Al recibir comando MQTT desde el frontend: Limpia y cambia de color.
 * 4. Al presionar cualquier botón: Recorre la lista de colores cíclicamente (1 -> 8 -> 1).
 * 5. Comando RESET / OFF: Apaga completamente la tira.
 * ====================================================================
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>

// --------------------------------------------------
// CONFIGURACION DE RED Y BROKER
// --------------------------------------------------
const char* WIFI_SSID     = "OctopyPB";
const char* WIFI_PASSWORD = "Octopy2025.";

const char* MQTT_SERVER   = "10.2.20.253";
const uint16_t MQTT_PORT  = 1883;
const char* MQTT_USER     = "OctopyPB";
const char* MQTT_PASSWORD = "Octopy2025.";

// Topicos MQTT
const char* TOPIC_COMMAND = "octopy/test/led";     // Escucha comandos desde el Frontend
const char* TOPIC_STATUS  = "octopy/test/status";  // Notifica cambios al Frontend

// --------------------------------------------------
// HARDWARE PINES
// --------------------------------------------------
#define PIN_WS2812     23
#define PIN_STATUS_LED 25
#define NUM_LEDS       36
#define RGB_BRIGHTNESS 80

#define PIN_BTN_A 18
#define PIN_BTN_B 19
#define PIN_BTN_C 21
#define PIN_BTN_D 22

Adafruit_NeoPixel strip(NUM_LEDS, PIN_WS2812, NEO_GRB + NEO_KHZ800);
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

// --------------------------------------------------
// PALETA DE COLORES DE PRUEBA (8 COLORES)
// --------------------------------------------------
struct ColorItem {
  const char* name;
  const char* hex;
  uint8_t r;
  uint8_t g;
  uint8_t b;
};

const ColorItem COLOR_PALETTE[] = {
  {"Rojo",       "#DC1414", 220, 20,  20},
  {"Verde",      "#14DC32", 20,  220, 50},
  {"Azul",       "#1450F0", 20,  80,  240},
  {"Amarillo",   "#F0C814", 240, 200, 20},
  {"Cyan",       "#14DCDC", 20,  220, 220},
  {"Magenta",    "#C814C8", 200, 20,  200},
  {"Naranja",    "#F06414", 240, 100, 20},
  {"Blanco",     "#B4B4B4", 180, 180, 180}
};

const uint8_t TOTAL_COLORS = sizeof(COLOR_PALETTE) / sizeof(COLOR_PALETTE[0]);
int currentColorIndex = -1; // -1 significa apagado / reset

// Variables para debounce de botones
unsigned long lastButtonPress = 0;
const unsigned long DEBOUNCE_MS = 250;

// --------------------------------------------------
// CONTROL DE LA TIRA WS2812B
// --------------------------------------------------
void clearStrip() {
  strip.clear();
  strip.show();
  delay(10); // Pausa de estabilización para el chip WS2812
}

void applyColor(uint8_t r, uint8_t g, uint8_t b) {
  // Siempre apagar y limpiar primero para evitar colores pegados
  clearStrip();

  if (r > 0 || g > 0 || b > 0) {
    for (uint16_t i = 0; i < NUM_LEDS; i++) {
      strip.setPixelColor(i, strip.Color(r, g, b));
    }
    strip.show();
  }
}

void setColorByIndex(int idx, bool notifyMQTT = true) {
  if (idx < 0 || idx >= TOTAL_COLORS) {
    currentColorIndex = -1;
    clearStrip();
    Serial.println("[LED] Tira apagada (RESET).");
  } else {
    currentColorIndex = idx;
    ColorItem c = COLOR_PALETTE[currentColorIndex];
    applyColor(c.r, c.g, c.b);
    Serial.printf("[LED] Color #%d: %s (%d, %d, %d)\n", currentColorIndex + 1, c.name, c.r, c.g, c.b);
  }

  if (notifyMQTT && mqtt.connected()) {
    StaticJsonDocument<256> doc;
    doc["event"] = (currentColorIndex == -1) ? "RESET" : "COLOR_CHANGED";
    doc["index"] = currentColorIndex;
    if (currentColorIndex >= 0) {
      doc["name"] = COLOR_PALETTE[currentColorIndex].name;
      doc["hex"]  = COLOR_PALETTE[currentColorIndex].hex;
      doc["r"]    = COLOR_PALETTE[currentColorIndex].r;
      doc["g"]    = COLOR_PALETTE[currentColorIndex].g;
      doc["b"]    = COLOR_PALETTE[currentColorIndex].b;
    }
    char buf[256];
    serializeJson(doc, buf);
    mqtt.publish(TOPIC_STATUS, buf);
  }
}

// --------------------------------------------------
// CALLBACK MQTT (COMANDOS DESDE EL FRONTEND)
// --------------------------------------------------
void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    Serial.print("[MQTT] Error al deserializar JSON: ");
    Serial.println(err.c_str());
    return;
  }

  const char* cmd = doc["cmd"] | "";
  Serial.printf("[MQTT RX] Comando recibido: %s\n", cmd);

  if (strcmp(cmd, "RESET") == 0 || strcmp(cmd, "OFF") == 0) {
    setColorByIndex(-1, true);
  } 
  else if (strcmp(cmd, "SET_INDEX") == 0) {
    int idx = doc["index"] | 0;
    setColorByIndex(idx, true);
  } 
  else if (strcmp(cmd, "SET_COLOR") == 0) {
    uint8_t r = doc["r"] | 0;
    uint8_t g = doc["g"] | 0;
    uint8_t b = doc["b"] | 0;
    applyColor(r, g, b);

    // Buscar si coincide con alguno de la paleta
    currentColorIndex = -1;
    for (int i = 0; i < TOTAL_COLORS; i++) {
      if (COLOR_PALETTE[i].r == r && COLOR_PALETTE[i].g == g && COLOR_PALETTE[i].b == b) {
        currentColorIndex = i;
        break;
      }
    }

    StaticJsonDocument<256> resp;
    resp["event"] = "COLOR_CHANGED";
    resp["index"] = currentColorIndex;
    resp["name"]  = doc["name"] | "Personalizado";
    resp["hex"]   = doc["hex"]  | "";
    resp["r"] = r; resp["g"] = g; resp["b"] = b;
    char buf[256];
    serializeJson(resp, buf);
    mqtt.publish(TOPIC_STATUS, buf);
  }
}

// --------------------------------------------------
// TRADUCTOR DE CODIGOS DE ERROR MQTT
// --------------------------------------------------
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

// --------------------------------------------------
// CONEXIÓN WIFI Y MQTT CON INDICADORES SERIALES
// --------------------------------------------------
void setupWiFi() {
  Serial.println("\n==================================================");
  Serial.print("[WiFi] Intentando conectar a la red: ");
  Serial.println(WIFI_SSID);
  Serial.print("[WiFi] MAC Address de este ESP32:     ");
  Serial.println(WiFi.macAddress());
  Serial.println("==================================================");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED) {
    digitalWrite(PIN_STATUS_LED, !digitalRead(PIN_STATUS_LED));
    delay(300);
    Serial.print(".");
    attempts++;

    if (attempts % 40 == 0) {
      Serial.printf("\n[WiFi] Todavía esperando enlace... Estado actual: %d\n", WiFi.status());
    }
  }

  digitalWrite(PIN_STATUS_LED, HIGH);
  Serial.println("\n");
  Serial.println("==================================================");
  Serial.println("  [OK] ¡WIFI CONECTADO EXITOSAMENTE!");
  Serial.print("  - Dirección IP:   "); Serial.println(WiFi.localIP());
  Serial.print("  - Máscara de red: "); Serial.println(WiFi.subnetMask());
  Serial.print("  - Gateway IP:     "); Serial.println(WiFi.gatewayIP());
  Serial.print("  - Potencia RSSI:  "); Serial.print(WiFi.RSSI()); Serial.println(" dBm");
  Serial.println("==================================================");
}

void connectMQTT() {
  int attempts = 0;
  while (!mqtt.connected()) {
    attempts++;
    String clientId = "ESP32-LED-TEST-" + String((uint32_t)ESP.getEfuseMac(), HEX);

    Serial.println("\n--------------------------------------------------");
    Serial.printf("[MQTT] Intento #%d de conexión al Broker...\n", attempts);
    Serial.printf("  - Servidor:   %s:%d\n", MQTT_SERVER, MQTT_PORT);
    Serial.printf("  - Client ID:  %s\n", clientId.c_str());
    if (strlen(MQTT_USER) > 0) {
      Serial.printf("  - Usuario:    %s (con contraseña)\n", MQTT_USER);
    } else {
      Serial.println("  - Modo:       Anónimo (sin usuario/password)");
    }

    bool ok = (strlen(MQTT_USER) > 0)
      ? mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASSWORD)
      : mqtt.connect(clientId.c_str());

    if (ok) {
      Serial.println("==================================================");
      Serial.println("  [OK] ¡MQTT CONECTADO EXITOSAMENTE!");
      Serial.printf("  - Tópico de escucha:   %s\n", TOPIC_COMMAND);
      Serial.printf("  - Tópico de respuesta: %s\n", TOPIC_STATUS);
      Serial.println("==================================================");

      mqtt.subscribe(TOPIC_COMMAND);

      // Notificar que está en línea
      StaticJsonDocument<128> doc;
      doc["event"] = "ONLINE";
      doc["ip"] = WiFi.localIP().toString();
      char buf[128];
      serializeJson(doc, buf);
      mqtt.publish(TOPIC_STATUS, buf);

      // Secuencia al conectar al broker: Azul por 1000ms y luego se apaga
      applyColor(0, 0, 150);
      delay(1000);
      clearStrip();
      Serial.println("[LED] Tira en Pin 23 apagada y lista para recibir comandos.\n");
    } else {
      int state = mqtt.state();
      Serial.printf("  [ERROR] Falló la conexión MQTT (rc = %d): %s\n", state, getMqttStateName(state));
      Serial.println("  Reintentando en 3 segundos...");
      delay(3000);
    }
  }
}

// --------------------------------------------------
// LECTURA DE BOTONES FISICOS (CICLO DE COLORES)
// --------------------------------------------------
void handleButtons() {
  // Cualquiera de los 4 botones avanza el ciclo
  int btnA = digitalRead(PIN_BTN_A);
  int btnB = digitalRead(PIN_BTN_B);
  int btnC = digitalRead(PIN_BTN_C);
  int btnD = digitalRead(PIN_BTN_D);

  bool anyPressed = (btnA == LOW || btnB == LOW || btnC == LOW || btnD == LOW);

  if (anyPressed && (millis() - lastButtonPress > DEBOUNCE_MS)) {
    lastButtonPress = millis();

    // Avanzar cíclicamente: 0 -> 1 -> 2 ... -> 7 -> 0
    int nextIndex = (currentColorIndex + 1) % TOTAL_COLORS;
    Serial.printf("[BOTON] Presionado! Cambiando a color %d (%s)\n", nextIndex + 1, COLOR_PALETTE[nextIndex].name);

    setColorByIndex(nextIndex, true);
  }
}

// --------------------------------------------------
// SETUP
// --------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n=== INICIANDO MODULO DE PRUEBA ESP32 ===");

  // Configurar Pines
  pinMode(PIN_STATUS_LED, OUTPUT);
  digitalWrite(PIN_STATUS_LED, LOW);

  pinMode(PIN_BTN_A, INPUT_PULLUP);
  pinMode(PIN_BTN_B, INPUT_PULLUP);
  pinMode(PIN_BTN_C, INPUT_PULLUP);
  pinMode(PIN_BTN_D, INPUT_PULLUP);

  // Inicializar NeoPixel
  strip.begin();
  strip.setBrightness(RGB_BRIGHTNESS);
  clearStrip();

  // Secuencia al encender: Verde en Pin 23 por 800ms y se apaga
  applyColor(0, 180, 0);
  delay(800);
  clearStrip();

  // Conectar WiFi
  setupWiFi();

  // Configurar MQTT
  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);
  mqtt.setBufferSize(512);

  connectMQTT();
}

// --------------------------------------------------
// LOOP
// --------------------------------------------------
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    setupWiFi();
  }

  if (!mqtt.connected()) {
    connectMQTT();
  }

  mqtt.loop();
  handleButtons();
  delay(10);
}
