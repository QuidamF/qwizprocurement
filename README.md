# 🎯 Trivia Día del Comprador — Quiz Procurement
> **Sistema interactivo de trivias para eventos corporativos con botoneras físicas ESP32 vía MQTT, sincronización en tiempo real por WebSockets y visualización audiovisual premium.**

---

## 📋 Descripción General

**Quiz Procurement** es una plataforma integral diseñada para dinámicas de trivias en vivo durante el evento *Día del Comprador* (Emendare Artem Emptionis). Permite que múltiples equipos compitan simultáneamente utilizando **botoneras físicas inalámbricas** (ESP32 con pulsadores arcade y retroalimentación lumínica) mientras el público y los participantes siguen el concurso en una **pantalla principal para proyector/TV** y el evento es operado fluidamente desde una **consola de moderador adaptada a tablets**.

---

## 🌟 Características Principales

### 🖥️ 1. Pantalla Principal (`/screen`)
* **Estética Cyber-Cósmica Iluminada:** Marco perimetral neón con respiración luminosa (`#6EC2BC` y `#38BDF8`), esquinas HUD y ambientación cósmica profunda.
* **Elementos Circulares Dinámicos:** Arcos orbitales y esferas planetarias flotantes inspiradas en la identidad corporativa oficial.
* **Etapas en Tiempo Real:** Portada con halo giratorio y levitación, visualización de preguntas 2x2 de alto contraste con insignias A-B-C-D iluminadas, revelación de respuestas correctas y tabla de resultados finales.
* **Telemetría Inferior:** Chips dinámicos que muestran en vivo qué equipos faltan por responder en cada pregunta.

### 🎮 2. Consola de Moderador (`/moderator`)
* **Diseño Responsive para Tablets:** Optimizado para pantallas táctiles con soporte Fullscreen nativo y panel lateral deslizable (drawer).
* **Control Total del Juego:** Botones de inicio, siguiente pregunta, revelar respuesta correcta, reiniciar y salto directo a cualquier pregunta del catálogo.
* **Atajos de Teclado:**
  * `Espacio` / `Enter`: Avanzar a la siguiente pregunta / Revelar respuesta.
  * `N`: Siguiente pregunta.
  * `P`: Pregunta previa.
  * `R`: Reiniciar concurso.
  * `?`: Ver lista de atajos.
* **Panel de Dispositivos Conectados:** Monitoreo en vivo de equipos conectados, estado de respuesta y señal.

### 📡 3. Gestor de Dispositivos y Red MQTT (`/devices`)
* **Detección Automática de Hardware Real:** Registro en tiempo real de botoneras físicas conforme se conectan por WiFi y MQTT.
* **Telemetría Completa:** Dirección IP, ID Físico (Dirección MAC), Calidad de señal (RSSI en dBm) y estado de respuesta.
* **Edición de Nombres en Vivo:** Permite renombrar dispositivos (ej. *OCTY-01* ➔ *Equipo Compras Norte*) con propagación instantánea a todas las pantallas.

### 🕹️ 4. Firmware ESP32 (`arduino/botonera/`)
* **Botoneras Inalámbricas:** Control con 4 botones físicos arcade (A, B, C, D) con debounce por hardware/software.
* **Retroalimentación RGB:** Anillo o LEDs NeoPixel indicadores de estado (espera, respuesta registrada, resultado correcto/incorrecto).
* **Protocolo MQTT:** Publicación de respuestas y suscripción a órdenes del servidor con reconexión automática resiliente.

---

## 🏗️ Arquitectura del Sistema

```text
       [ Botonera ESP32 #1 ]       [ Botonera ESP32 #2 ]       [ Botonera ESP32 #N ]
                 │                           │                           │
                 └─────────────── WiFi / MQTT ───────────────────────────┘
                                             │
                                     [ Broker MQTT ] (Mosquitto :1883)
                                             │
                                  [ backend/mqtt_service.py ]
                                             │
                                   [ GameEngine (Python) ]
                                             │
                           ┌─────────────────┴─────────────────┐
                    WebSockets /ws                     WebSockets /ws
                           │                                   │
               [ /screen (Proyector/TV) ]           [ /moderator (Tablet) ]
```

---

## 📁 Estructura del Repositorio

```text
QuizProcurement/
├── arduino/                        # Firmware para microcontroladores
│   └── botonera/
│       └── botonera.ino            # Código Arduino C++ para botoneras ESP32
├── backend/                        # Servidor central FastAPI
│   ├── app.py                      # Rutas REST, WebSockets y servidor estático
│   ├── game_engine.py              # Máquina de estados del juego y temporizadores
│   ├── models.py                   # Modelos de datos Pydantic
│   └── mqtt_service.py             # Cliente puente MQTT Paho
├── frontend/                       # Interfaces web
│   ├── static/
│   │   ├── css/                    # Hojas de estilo (screen, moderator, devices, common)
│   │   ├── js/                     # Lógica frontend y clientes WebSocket
│   │   └── img/                    # Logotipos y recursos gráficos vectoriales
│   └── templates/                  # Vistas HTML (screen, moderator, devices)
├── Referencias/                    # Recursos visuales y especificaciones del evento
├── test/                           # Scripts de prueba y emuladores de hardware
│   ├── mock_esp32.py               # Emulador de botonera ESP32 en Python
│   └── test_mqtt_device.py         # Pruebas de conectividad MQTT
├── preguntas.json                  # Catálogo de 30 preguntas de Compras y Abastecimiento
├── preguntas.md                    # Documento de referencia de preguntas y respuestas
├── requirements.txt                # Dependencias Python
└── run.sh                          # Script ejecutable de inicio automático
```

---

## 🚀 Requisitos e Instalación

### Requisitos Previos
* **Python 3.10+**
* **Broker MQTT** (ej. Eclipse Mosquitto en localhost:1883 o IP de red local)
* **Arduino IDE / ESP-IDF** (para compilar y cargar el firmware a las placas ESP32)

### 1. Iniciar el Servidor con un Solo Comando

El script `run.sh` crea automáticamente el entorno virtual (`venv`), instala las dependencias necesarias y levanta Uvicorn:

```bash
chmod +x run.sh
./run.sh
```

El servidor estará accesible en:
* **Pantalla de Proyección:** [http://localhost:8000/screen](http://localhost:8000/screen)
* **Consola del Moderador:** [http://localhost:8000/moderator](http://localhost:8000/moderator)
* **Gestor de Dispositivos:** [http://localhost:8000/devices](http://localhost:8000/devices)
* **Documentación OpenAPI:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📡 Tópicos MQTT

| Tópico | Dirección | Descripción |
|---|---|---|
| `quiz/device/{id}/register` | ESP32 ➔ Servidor | Registro de dispositivo con MAC, IP y RSSI |
| `quiz/device/{id}/status` | ESP32 ➔ Servidor | Latido (Heartbeat) de estado en línea |
| `quiz/device/{id}/answer` | ESP32 ➔ Servidor | Envío de opción seleccionada (`A`, `B`, `C` o `D`) |
| `quiz/device/{id}/command` | Servidor ➔ ESP32 | Órdenes de LED/animación (`LED_OPEN`, `LED_CORRECT`, `LED_RESET`) |

---

## 🍓 Despliegue en Raspberry Pi (Zero 2 W / 3 / 4 / 5) con PM2 y Modo Kiosko

### 1. Instalación de Mosquitto MQTT Broker como Servicio del Sistema
Para que Mosquitto inicie automáticamente con la Raspberry Pi:

```bash
# Instalar broker y cliente
sudo apt update
sudo apt install -y mosquitto mosquitto-clients

# Configurar para permitir conexiones de botoneras en red local
sudo tee /etc/mosquitto/conf.d/default.conf > /dev/null << 'EOF'
listener 1883
allow_anonymous true
EOF

# Habilitar e iniciar servicio systemd
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto

# Verificar estado
sudo systemctl status mosquitto
```

### 2. Instalación de PM2 y Chromium
```bash
# Instalar Chromium y herramientas de pantalla
sudo apt install -y chromium-browser x11-xserver-utils

# Instalar Node.js y PM2
sudo apt install -y nodejs npm
sudo npm install -g pm2
```

### 3. Configuración de Autoarranque con PM2 (`ecosystem.config.json`)
El archivo `ecosystem.config.json` administra tanto el backend FastAPI como el script `start_kiosk.sh` (con delay de 20 segundos y verificación activa de salud):

```bash
# Iniciar servicios con PM2
pm2 start ecosystem.config.json

# Guardar la lista de procesos activos
pm2 save

# Configurar inicio automático en el arranque del sistema (ejecutar el comando que indique PM2)
pm2 startup
```

---

## 👥 Créditos y Licencia

Desarrollado para la dinámica corporativa del **Día del Comprador** — *Emendare Artem Emptionis*.
