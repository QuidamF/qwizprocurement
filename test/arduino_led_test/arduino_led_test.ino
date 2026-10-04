/*
 * ====================================================================
 * OCTOPY - TEST LED ARDUINO (WS2812B / NEOPIXEL A 5V)
 * ====================================================================
 * Prueba ciclica de colores para tira WS2812B conectada a Arduino
 * (Arduino Uno, Nano, Mega o compatible a 5V nativos).
 *
 * ESPECIFICACIONES:
 * - Pin de Datos Tira: Pin Digital 6 (Cambiable segun tu conexion)
 * - Cantidad de LEDs:  36 LEDs
 * - Tiempo por color:  4 Segundos
 * - Salida Serial:     115200 baudios (Muestra color activo y codigo RGB)
 * - Proteccion:        Limpia bufer antes de cada cambio para evitar
 *                      colores pegados.
 * ====================================================================
 */

#include <Adafruit_NeoPixel.h>

// --------------------------------------------------
// CONFIGURACION DE HARDWARE
// --------------------------------------------------
#define PIN_WS2812     6    // Pin digital del Arduino conectado a DIN de la tira
#define NUM_LEDS       36   // Longitud de la tira (36 LEDs)
#define RGB_BRIGHTNESS 90   // Brillo (0 a 255)

Adafruit_NeoPixel strip(NUM_LEDS, PIN_WS2812, NEO_GRB + NEO_KHZ800);

// --------------------------------------------------
// DEFINICION DE COLORES
// --------------------------------------------------
struct ColorDef {
  const char* name;
  const char* hex;
  uint8_t r;
  uint8_t g;
  uint8_t b;
};

const ColorDef PALETTE[] = {
  {"1. ROJO",         "#DC1414", 220, 20,  20},
  {"2. VERDE",        "#14DC32", 20,  220, 50},
  {"3. AZUL",         "#1450F0", 20,  80,  240},
  {"4. AMARILLO",     "#F0C814", 240, 200, 20},
  {"5. CYAN / AQUA",  "#14DCDC", 20,  220, 220},
  {"6. MAGENTA",      "#C814C8", 200, 20,  200},
  {"7. NARANJA",      "#F06414", 240, 100, 20},
  {"8. BLANCO",       "#B4B4B4", 180, 180, 180},
  {"9. APAGADO/OFF",  "#000000", 0,   0,   0}
};

const uint8_t TOTAL_COLORS = sizeof(PALETTE) / sizeof(PALETTE[0]);
int currentColorIndex = 0;

// --------------------------------------------------
// FUNCIONES DE CONTROL DE LA TIRA
// --------------------------------------------------
void clearStrip() {
  strip.clear();
  strip.show();
  delay(15); // Pausa de estabilizacion (latch) para los chips WS2812
}

void applyColor(uint8_t r, uint8_t g, uint8_t b) {
  // Limpiar primero fisicamente el bufer para evitar residuos o pixeles pegados
  clearStrip();

  if (r > 0 || g > 0 || b > 0) {
    for (uint16_t i = 0; i < NUM_LEDS; i++) {
      strip.setPixelColor(i, strip.Color(r, g, b));
    }
    strip.show();
  }
}

// --------------------------------------------------
// SETUP
// --------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(300);

  Serial.println();
  Serial.println(F("=================================================="));
  Serial.println(F("   OCTOPY - TEST LED ARDUINO (WS2812B / 5V)"));
  Serial.println(F("=================================================="));
  Serial.print(F("Pin de Datos:  Digital ")); Serial.println(PIN_WS2812);
  Serial.print(F("Num de LEDs:   "));        Serial.println(NUM_LEDS);
  Serial.print(F("Tiempo color:  4 segundos"));
  Serial.println();
  Serial.println(F("=================================================="));

  strip.begin();
  strip.setBrightness(RGB_BRIGHTNESS);
  clearStrip();

  Serial.println(F("Iniciando secuencia ciclica...\n"));
}

// --------------------------------------------------
// LOOP PRINCIPAL (CICLO CADA 4 SEGUNDOS)
// --------------------------------------------------
void loop() {
  ColorDef col = PALETTE[currentColorIndex];

  // Imprimir por terminal Serial que color esta activo
  Serial.println(F("--------------------------------------------------"));
  Serial.print(F(">> MOSTRANDO: "));
  Serial.println(col.name);
  Serial.print(F("   HEX: "));
  Serial.print(col.hex);
  Serial.print(F(" | RGB: ("));
  Serial.print(col.r);
  Serial.print(F(", "));
  Serial.print(col.g);
  Serial.print(F(", "));
  Serial.print(col.b);
  Serial.println(F(")"));
  Serial.println(F("   Duracion: 4 segundos..."));

  // Aplicar el color a la tira fisica
  applyColor(col.r, col.g, col.b);

  // Esperar los 4 segundos completos con conteo en consola
  for (int seg = 4; seg > 0; seg--) {
    delay(1000);
    Serial.print(F("."));
  }
  Serial.println();

  // Avanzar al siguiente color de forma ciclica (1 -> 9 -> 1)
  currentColorIndex = (currentColorIndex + 1) % TOTAL_COLORS;
}
