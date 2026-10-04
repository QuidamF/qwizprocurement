# Maqueta y arquitectura base --- Sistema de Quiz con Botoneras

## Objetivo

Construir primero una **maqueta funcional cliente-servidor web** de un
sistema de preguntas y respuestas para un juego tipo concurso.

La primera versión debe permitir probar la experiencia completa sin
depender todavía de las botoneras físicas, MQTT ni ESP32.

La evolución prevista es:

1.  Servidor / backend
2.  Panel del moderador
3.  Pantalla principal del juego / preguntas
4.  Interfaz de botonera simulada
5.  Integración de MQTT
6.  Integración de ESP32 como botoneras físicas
7.  Operación local mediante Raspberry Pi

------------------------------------------------------------------------

# 1. Concepto general

El sistema tendrá un servidor que contiene la lógica del juego.

Habrá tres interfaces principales:

### Servidor / Backend

Responsable de:

-   administrar el estado de la partida;
-   almacenar preguntas;
-   administrar jugadores o botoneras;
-   recibir respuestas;
-   validar respuestas;
-   controlar tiempos;
-   determinar resultados;
-   enviar actualizaciones a los clientes.

### Moderador

Interfaz utilizada por la persona que controla el juego.

Debe permitir:

-   iniciar una partida;
-   seleccionar o avanzar preguntas;
-   iniciar una pregunta;
-   cerrar una pregunta;
-   visualizar respuestas recibidas;
-   visualizar qué botonera respondió primero;
-   mostrar la respuesta correcta;
-   avanzar a la siguiente pregunta;
-   visualizar puntuaciones;
-   reiniciar una partida.

### Pantalla de juego

Interfaz que se muestra al público o participantes.

Debe mostrar:

-   pregunta actual;
-   opciones A/B/C/D;
-   temporizador;
-   estado de la pregunta;
-   resultados;
-   puntuaciones;
-   mensajes como "tiempo agotado", "respuesta correcta", etc.

### Botonera simulada

Antes de construir el hardware físico se utilizará una interfaz web que
represente una botonera.

Cada botonera tendrá:

-   identificación;
-   botones A, B, C y D;
-   estado actual;
-   indicador de respuesta enviada;
-   bloqueo después de responder, si la lógica del juego lo requiere.

Esto permitirá probar toda la lógica del sistema usando solamente
navegadores.

------------------------------------------------------------------------

# 2. ¿Por qué comenzar con una maqueta web?

La primera etapa debe validar la **experiencia y lógica del juego**, no
el hardware.

Si primero se construyen ESP32, MQTT, Wi-Fi y botoneras físicas, se
mezclan varios problemas:

-   conectividad;
-   identificación de dispositivos;
-   latencia;
-   firmware;
-   MQTT;
-   interfaz;
-   reglas del juego;
-   puntuación;
-   sincronización.

La maqueta permite comprobar primero que:

> Moderador → servidor → pantalla → botoneras simuladas → servidor →
> resultado

funciona correctamente.

Una vez que la lógica esté validada, la botonera física solamente tendrá
que sustituir a la botonera web como fuente de eventos.

------------------------------------------------------------------------

# 3. Arquitectura inicial

``` text
                         ┌─────────────────────┐
                         │      SERVIDOR       │
                         │                     │
                         │ Backend / API       │
                         │ Game Engine         │
                         │ Base de datos       │
                         └──────────┬──────────┘
                                    │
                   ┌────────────────┼────────────────┐
                   │                │                │
                   ▼                ▼                ▼
          ┌────────────────┐ ┌───────────────┐ ┌────────────────┐
          │   MODERADOR    │ │    PANTALLA   │ │   BOTONERAS    │
          │                │ │    DEL JUEGO  │ │   SIMULADAS    │
          │ Control juego  │ │                │ │                │
          │ Preguntas      │ │ Pregunta       │ │ A B C D        │
          │ Resultados     │ │ Opciones       │ │ BOT-01         │
          └────────────────┘ │ Timer          │ │ BOT-02         │
                             │ Resultados     │ │ ...            │
                             └───────────────┘ └────────────────┘
```

En esta etapa todos los clientes pueden ser navegadores conectados al
mismo servidor.

------------------------------------------------------------------------

# 4. Comunicación cliente-servidor

Para la maqueta se recomienda separar dos tipos de comunicación.

## HTTP / REST

Para operaciones como:

-   obtener preguntas;
-   crear partidas;
-   consultar configuración;
-   registrar jugadores/botoneras;
-   consultar resultados.

Ejemplos:

``` text
GET  /api/questions
POST /api/games
GET  /api/games/{game_id}
```

## WebSocket

Para eventos en tiempo real.

Ejemplos:

``` text
moderador inicia pregunta
        ↓
servidor
        ↓
pantalla actualiza pregunta

botonera simulada responde
        ↓
servidor
        ↓
moderador recibe respuesta
        ↓
pantalla recibe actualización
```

La razón para utilizar WebSocket es que el juego tiene eventos que deben
propagarse inmediatamente a varios clientes.

------------------------------------------------------------------------

# 5. Flujo básico de una pregunta

## Estado inicial

El juego está esperando.

``` text
WAITING
```

El moderador selecciona una pregunta.

``` text
QUESTION_SELECTED
```

El moderador inicia la pregunta.

``` text
ACTIVE
```

La pantalla muestra:

``` text
Pregunta:
¿Cuál es la capital de Francia?

A) Madrid
B) París
C) Roma
D) Berlín
```

Los participantes pueden responder.

Una botonera simulada envía:

``` json
{
  "device_id": "BOT-03",
  "answer": "B"
}
```

El servidor recibe la respuesta y registra:

-   botonera;
-   respuesta;
-   hora de recepción;
-   pregunta;
-   número de respuesta;
-   estado.

Cuando termina el tiempo:

``` text
TIMEOUT
```

El servidor determina:

-   respuestas recibidas;
-   respuesta correcta;
-   participantes acertados;
-   puntuación;
-   orden de respuesta.

Finalmente:

``` text
RESULT
```

La pantalla muestra el resultado y el moderador puede avanzar.

------------------------------------------------------------------------

# 6. Identificación de las botoneras

En la maqueta no es necesario tener hardware.

Cada botonera simulada puede tener un ID:

``` text
BOT-01
BOT-02
BOT-03
...
BOT-10
```

La arquitectura debe conservar desde el principio la idea de una
identidad independiente del navegador.

Por ejemplo:

``` json
{
  "device_id": "BOT-07",
  "name": "Equipo 7",
  "status": "online"
}
```

Esto permitirá sustituir posteriormente:

``` text
Botonera web BOT-07
```

por:

``` text
ESP32 físico BOT-07
```

sin cambiar la lógica principal del juego.

------------------------------------------------------------------------

# 7. Pregunta y respuesta

Una pregunta debería tener una estructura similar a:

``` json
{
  "id": 152,
  "text": "¿Cuál es la capital de Francia?",
  "options": {
    "A": "Madrid",
    "B": "París",
    "C": "Roma",
    "D": "Berlín"
  },
  "correct_answer": "B",
  "time_limit": 15
}
```

El servidor es quien debe conocer la respuesta correcta.

El cliente no debería decidir si una respuesta es correcta.

------------------------------------------------------------------------

# 8. Evento de respuesta

La respuesta de una botonera simulada puede manejarse como:

``` json
{
  "game_id": "GAME-001",
  "question_id": 152,
  "device_id": "BOT-07",
  "answer": "C",
  "sequence": 381
}
```

El servidor agrega su propio timestamp de recepción.

No se debe confiar exclusivamente en el timestamp enviado por el cliente
para determinar el orden.

------------------------------------------------------------------------

# 9. Primera respuesta

Si el juego requiere determinar quién respondió primero, el servidor
debe ser la autoridad.

Ejemplo:

``` text
BOT-03 → respuesta B → servidor recibe 10:31:02.105
BOT-07 → respuesta C → servidor recibe 10:31:02.240
BOT-01 → respuesta B → servidor recibe 10:31:02.311
```

El servidor determina el orden:

``` text
1. BOT-03
2. BOT-07
3. BOT-01
```

La interfaz puede mostrar este orden al moderador.

------------------------------------------------------------------------

# 10. Estado de una botonera

Cada botonera puede tener estados como:

``` text
ONLINE
OFFLINE
WAITING
ANSWERED
LOCKED
```

Ejemplo:

``` text
BOT-01  ONLINE   WAITING
BOT-02  ONLINE   ANSWERED
BOT-03  ONLINE   ANSWERED
BOT-04  OFFLINE
```

Esto será especialmente útil cuando posteriormente se integren las
botoneras físicas.

------------------------------------------------------------------------

# 11. Estado del juego

Se recomienda utilizar una máquina de estados sencilla.

``` text
IDLE
  ↓
LOBBY
  ↓
QUESTION_READY
  ↓
ACTIVE
  ↓
TIMEOUT
  ↓
RESULT
  ↓
NEXT QUESTION
  ↓
ACTIVE
```

No se debe permitir que cada cliente modifique libremente el estado.

El servidor debe ser la autoridad sobre el estado de la partida.

------------------------------------------------------------------------

# 12. Responsabilidades de cada interfaz

## Moderador

Puede:

``` text
Crear partida
↓
Seleccionar pregunta
↓
Iniciar pregunta
↓
Cerrar pregunta
↓
Mostrar resultado
↓
Siguiente pregunta
↓
Finalizar partida
```

No debe calcular por su cuenta la puntuación ni decidir qué respuesta
fue válida.

------------------------------------------------------------------------

## Pantalla

Es principalmente una interfaz de presentación.

Recibe eventos:

``` text
GAME_STARTED
QUESTION_STARTED
ANSWER_RECEIVED
TIME_UPDATE
QUESTION_FINISHED
RESULT
GAME_FINISHED
```

Y actualiza la interfaz.

------------------------------------------------------------------------

## Botonera simulada

Solo necesita generar eventos:

``` text
BUTTON_A
BUTTON_B
BUTTON_C
BUTTON_D
```

Ejemplo:

``` text
BOT-05
    ↓
presiona C
    ↓
WebSocket
    ↓
servidor
```

No debe contener las reglas de negocio.

------------------------------------------------------------------------

# 13. ¿Dónde deben vivir las reglas?

Las reglas deben estar en el servidor.

Por ejemplo:

``` text
¿La pregunta está activa?
¿La botonera puede responder?
¿Ya respondió?
¿La respuesta llegó dentro del tiempo?
¿La respuesta es correcta?
¿Cuántos puntos obtiene?
¿Puede volver a responder?
```

El frontend solamente presenta el estado y envía acciones.

Esto es importante porque posteriormente el ESP32 no debe necesitar
conocer las reglas completas del juego.

------------------------------------------------------------------------

# 14. Segunda etapa: MQTT

Cuando la maqueta web funcione, se incorpora MQTT.

La arquitectura evolucionaría a:

``` text
                         ┌─────────────────────┐
                         │      SERVIDOR       │
                         │                     │
                         │ Game Engine         │
                         │ API                 │
                         │ WebSocket           │
                         └──────────┬──────────┘
                                    │
                              MQTT Broker
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
                 ▼                  ▼                  ▼
             ESP32-01           ESP32-02           ESP32-10
```

El navegador de la botonera simulada será reemplazado por un ESP32.

La lógica del servidor no debería cambiar.

------------------------------------------------------------------------

# 15. Raspberry Pi como servidor local

Para la versión física, una Raspberry Pi puede funcionar como servidor
local.

Componentes:

``` text
Raspberry Pi
│
├── Wi-Fi Hotspot
│
├── MQTT Broker
│
├── Backend
│
├── Base de datos
│
├── WebSocket
│
└── Frontend
```

Los ESP32 se conectan al Wi-Fi creado por la Raspberry Pi.

Esto evita depender de Internet durante el evento.

------------------------------------------------------------------------

# 16. Comunicación con MQTT

Ejemplo de publicación de respuesta:

``` text
quiz/device/BOT-07/answer
```

Payload:

``` json
{
  "question_id": 152,
  "button": "C",
  "sequence": 381
}
```

El servidor procesa la respuesta.

Posteriormente puede enviar una respuesta al dispositivo:

``` text
quiz/device/BOT-07/feedback
```

Payload:

``` json
{
  "question_id": 152,
  "result": "incorrect",
  "led": "red"
}
```

Esto permite que la botonera tenga retroalimentación visual.

------------------------------------------------------------------------

# 17. Comunicación bidireccional

Una ventaja importante de MQTT es que la comunicación no tiene que ser
solamente:

``` text
ESP32 → servidor
```

También puede ser:

``` text
servidor → ESP32
```

Por ejemplo:

``` text
Pregunta termina
       ↓
Servidor determina resultado
       ↓
MQTT
       ↓
BOT-07
       ↓
LED rojo
```

O:

``` text
Respuesta correcta
       ↓
MQTT
       ↓
BOT-03
       ↓
LED verde
```

------------------------------------------------------------------------

# 18. Identidad física vs identidad lógica

La arquitectura debe distinguir:

### Identidad física

Representa al hardware.

Ejemplo:

``` text
MAC / chip ID
```

### Identidad lógica

Representa el lugar que ocupa dentro del juego.

Ejemplo:

``` text
BOT-07
```

Esto permite que un ESP32 físico pueda ser reasignado.

Ejemplo:

``` text
ESP32 ABC123 → BOT-07
```

y posteriormente:

``` text
ESP32 ABC123 → BOT-03
```

sin tener que cambiar necesariamente el firmware.

------------------------------------------------------------------------

# 19. Registro de dispositivos

Cuando posteriormente se conecte un ESP32, podría anunciarse:

``` json
{
  "hardware_id": "84:F7:03:12:AB:91",
  "device_type": "quiz-button",
  "firmware": "1.0.0"
}
```

El servidor podría asociarlo con:

``` text
BOT-07
```

La administración de esa asociación debe vivir en el servidor.

------------------------------------------------------------------------

# 20. Arquitectura final prevista

``` text
                        ┌──────────────────────────┐
                        │       RASPBERRY PI       │
                        │                          │
                        │  Wi-Fi AP                │
                        │  MQTT Broker             │
                        │  Backend                 │
                        │  Game Engine             │
                        │  Database                │
                        │  WebSocket               │
                        └────────────┬─────────────┘
                                     │
          ┌──────────────────────────┼──────────────────────────┐
          │                          │                          │
          ▼                          ▼                          ▼
 ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
 │   MODERADOR     │       │     PANTALLA    │       │    BOTONERAS    │
 │                 │       │                 │       │                 │
 │ Control juego   │       │ Pregunta        │       │ ESP32           │
 │ Preguntas       │       │ Opciones        │       │ A B C D         │
 │ Resultados      │       │ Timer           │       │ LED             │
 └─────────────────┘       │ Resultados      │       └─────────────────┘
                           └─────────────────┘
                                                               │
                                                     MQTT / Wi-Fi
```

------------------------------------------------------------------------

# 21. Orden recomendado de desarrollo

## Fase 1 --- Maqueta web

Construir solamente:

``` text
Servidor
Moderador
Pantalla
Botonera simulada
```

Objetivo:

> Poder jugar una partida completa utilizando únicamente navegadores.

------------------------------------------------------------------------

## Fase 2 --- Reglas del juego

Implementar:

-   preguntas;
-   opciones;
-   temporizador;
-   respuestas;
-   validación;
-   puntuación;
-   bloqueo de respuestas;
-   orden de respuestas;
-   estados del juego;
-   resultados.

------------------------------------------------------------------------

## Fase 3 --- Comunicación en tiempo real

Implementar WebSocket entre:

``` text
Servidor ↔ Moderador
Servidor ↔ Pantalla
Servidor ↔ Botoneras simuladas
```

------------------------------------------------------------------------

## Fase 4 --- MQTT

Agregar:

``` text
MQTT Broker
```

y reemplazar progresivamente la botonera web por clientes MQTT
simulados.

Primero se puede probar MQTT sin hardware.

------------------------------------------------------------------------

## Fase 5 --- ESP32

Implementar firmware con:

``` text
Wi-Fi
MQTT
A/B/C/D
LED
device_id
sequence
reconexión
```

------------------------------------------------------------------------

## Fase 6 --- Raspberry Pi

Convertir la Raspberry Pi en la plataforma de operación local:

``` text
Wi-Fi Hotspot
+
MQTT
+
Backend
+
Database
+
Frontend
```

------------------------------------------------------------------------

# 22. Preguntas y respuestas de diseño

## ¿ESP-NOW o Wi-Fi + MQTT?

Para este proyecto, ambas opciones son técnicamente posibles.

ESP-NOW tiene sentido cuando se busca comunicación directa entre ESP32
sin depender de una red Wi-Fi convencional.

Sin embargo, para una aplicación con alrededor de 10 botoneras y
necesidad de comunicación bidireccional, Wi-Fi local + MQTT simplifica
la arquitectura.

La Raspberry Pi puede proporcionar la red local y el broker MQTT.

------------------------------------------------------------------------

## ¿Por qué no hacer POST desde cada ESP32?

Se puede hacer:

``` text
ESP32 → HTTP POST → servidor
```

pero para un juego interactivo introduce una comunicación más orientada
a petición/respuesta.

MQTT permite manejar naturalmente:

``` text
ESP32 → evento → broker → servidor
```

y también:

``` text
servidor → comando → broker → ESP32
```

Esto es conveniente para LEDs, estados y comandos.

------------------------------------------------------------------------

## ¿Necesitamos Internet?

No necesariamente.

La partida puede funcionar completamente dentro de la red local:

``` text
ESP32
 ↓
Wi-Fi local
 ↓
Raspberry Pi
 ↓
Servidor
```

Internet podría utilizarse posteriormente para:

-   sincronizar resultados;
-   enviar estadísticas;
-   administrar contenido;
-   respaldar partidas;
-   acceder remotamente.

Pero no debería ser un requisito para ejecutar una partida local.

------------------------------------------------------------------------

## ¿Cuántas botoneras puede manejar?

Para una primera implementación de aproximadamente 10 botoneras, la
carga de mensajes es muy pequeña.

El problema principal no será el volumen de datos sino diseñar
correctamente:

-   concurrencia;
-   reconexiones;
-   identificación;
-   estados;
-   orden de respuestas;
-   sincronización.

------------------------------------------------------------------------

## ¿El ESP32 necesita saber cuál es la respuesta correcta?

No.

El ESP32 solamente debe comunicar:

``` text
BOT-07
presionó C
```

El servidor determina:

``` text
¿C es correcta?
¿Cuántos puntos obtiene?
¿Puede responder?
¿La respuesta llegó a tiempo?
```

Esto mantiene la lógica centralizada.

------------------------------------------------------------------------

## ¿La botonera física necesita Internet?

No.

Solo necesita conectarse a la red local de la Raspberry Pi.

------------------------------------------------------------------------

## ¿Qué ocurre si un ESP32 pierde conexión?

El dispositivo debe implementar reconexión automática.

El servidor debe poder detectar:

``` text
ONLINE
OFFLINE
```

MQTT puede utilizar mecanismos como Last Will and Testament para
informar la desconexión de un dispositivo.

------------------------------------------------------------------------

## ¿La interfaz web debe conocer MQTT?

Idealmente no.

La interfaz web debería comunicarse con el backend mediante
HTTP/WebSocket.

El backend será el encargado de comunicarse con MQTT.

Así se mantiene esta separación:

``` text
Frontend
   ↓
Backend / Game Engine
   ↓
MQTT
   ↓
ESP32
```

------------------------------------------------------------------------

# 23. Principio fundamental de la arquitectura

La botonera no debe ser el centro del sistema.

El centro debe ser el **Game Engine**.

La botonera es solamente un dispositivo de entrada.

Actualmente:

``` text
Botonera Web
```

Posteriormente:

``` text
ESP32 + MQTT
```

Ambas deben producir esencialmente el mismo evento:

``` json
{
  "device_id": "BOT-07",
  "button": "C"
}
```

Si esto se diseña correctamente, la migración de maqueta a hardware será
principalmente un cambio de transporte y no una reescritura del juego.

------------------------------------------------------------------------

# 24. Prompt inicial para Gemini

Utilizar el siguiente contexto como punto de partida:

> Quiero construir una maqueta web de un sistema de quiz competitivo con
> hasta 10 botoneras.
>
> Primero NO quiero implementar ESP32 ni MQTT. Quiero validar la
> arquitectura y experiencia del juego utilizando únicamente navegador +
> servidor.
>
> El sistema debe tener cuatro componentes:
>
> 1.  Backend/servidor con la lógica del juego.
> 2.  Panel de moderador para controlar la partida.
> 3.  Pantalla de juego para mostrar preguntas, opciones, temporizador y
>     resultados.
> 4.  Botoneras simuladas como interfaces web independientes,
>     identificadas como BOT-01, BOT-02, etc.
>
> La comunicación en tiempo real debe utilizar WebSocket.
>
> El servidor debe ser la autoridad sobre:
>
> -   estado de la partida;
> -   pregunta activa;
> -   tiempo;
> -   respuestas;
> -   validación;
> -   orden de recepción;
> -   puntuación;
> -   resultados.
>
> Las interfaces cliente no deben contener las reglas de negocio.
>
> Diseña primero una arquitectura mínima pero extensible que
> posteriormente permita sustituir las botoneras web por ESP32
> conectados mediante MQTT.
>
> No implementes todavía MQTT ni hardware.
>
> Quiero poder ejecutar una partida completa con navegadores:
>
> Moderador → inicia pregunta → pantalla muestra pregunta → botoneras
> simuladas responden → servidor procesa → pantalla y moderador reciben
> resultados → siguiente pregunta.
>
> Prioriza una arquitectura sencilla, mantenible y fácil de probar antes
> que una arquitectura sobredimensionada.

------------------------------------------------------------------------

# 25. Criterio para saber si la Fase 1 está terminada

La primera fase estará terminada cuando sea posible abrir varias
ventanas/navegadores y realizar algo equivalente a:

``` text
┌──────────────────┐
│ MODERADOR        │
│                  │
│ Pregunta 1       │
│ [Iniciar]        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ PANTALLA         │
│                  │
│ ¿2 + 2 = ?       │
│                  │
│ A) 3             │
│ B) 4             │
│ C) 5             │
│ D) 6             │
│                  │
│     00:12        │
└──────────────────┘

┌──────────────────┐
│ BOT-01           │
│                  │
│ [ A ] [ B ]      │
│ [ C ] [ D ]      │
└──────────────────┘

┌──────────────────┐
│ BOT-02           │
│                  │
│ [ A ] [ B ]      │
│ [ C ] [ D ]      │
└──────────────────┘
```

Y que el servidor pueda registrar:

``` text
Pregunta iniciada
↓
BOT-02 respondió B
↓
BOT-01 respondió C
↓
Tiempo agotado
↓
B es correcta
↓
BOT-02 +100 puntos
↓
Mostrar resultado
↓
Siguiente pregunta
```

Cuando esto funcione de forma estable, tiene sentido comenzar la
integración de MQTT y posteriormente de las botoneras ESP32.
