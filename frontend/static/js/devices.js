/**
 * Device Manager & MQTT Diagnostics Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  const tableBody = document.getElementById('devices-table-body');
  const devicesCountBadge = document.getElementById('devices-count-badge');
  const mqttBrokerBadge = document.getElementById('mqtt-broker-badge');
  const mqttTerminal = document.getElementById('mqtt-terminal');

  const simTargetSelect = document.getElementById('sim-target-device');
  const simHwMacInput = document.getElementById('sim-hw-mac');
  const btnSimRegister = document.getElementById('btn-sim-register');
  const simKeyBtns = document.querySelectorAll('.sim-key-btn');

  let ws = null;
  let currentDevices = [];

  function logTerminal(topic, message) {
    const timeStr = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = 'term-entry';
    entry.innerHTML = `<span class="term-time">[${timeStr}]</span> <span class="term-topic">${topic}</span>: ${message}`;
    mqttTerminal.appendChild(entry);
    mqttTerminal.scrollTop = mqttTerminal.scrollHeight;
  }

  function renderDevices(devices) {
    currentDevices = devices || [];
    tableBody.innerHTML = '';
    devicesCountBadge.textContent = `${currentDevices.length} Dispositivos`;

    if (currentDevices.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 36px 16px;">
            <div style="font-size: 1.6rem; margin-bottom: 8px;">📡</div>
            <strong style="color: #FFFFFF;">Sin dispositivos conectados</strong>
            <p style="font-size: 0.85rem; margin: 4px 0 0 0; color: var(--text-dim);">
              Conecta las botoneras físicas ESP32 vía MQTT o abre un buzzer web desde un dispositivo con IP propia.
            </p>
          </td>
        </tr>`;
      return;
    }

    currentDevices.forEach((dev) => {
      const row = document.createElement('tr');
      const isMqtt = dev.connection_type === 'MQTT';
      const isOnline = dev.status !== 'OFFLINE';

      const connBadge = isMqtt 
        ? `<span class="conn-tag conn-mqtt">⚡ ESP32 / MQTT</span>` 
        : `<span class="conn-tag conn-web">🌐 Web Browser</span>`;

      const hwText = dev.hardware_id 
        ? `<span class="hw-badge">${dev.hardware_id}</span>` 
        : `<span style="color: var(--text-dim); font-size: 0.8rem;">No asignado</span>`;

      const ipText = dev.ip_address || '127.0.0.1';
      const fwText = dev.firmware ? ` (${dev.firmware})` : '';
      const wifiTag = dev.wifi_rssi ? `<div style="font-size: 0.75rem; color: #34D399;">📶 ${dev.wifi_rssi} dBm</div>` : '';

      const statusBadge = isOnline
        ? `<span class="badge badge-success">ONLINE</span>`
        : `<span class="badge badge-danger">OFFLINE</span>`;

      row.innerHTML = `
        <td><strong style="color: var(--accent-teal); font-family: var(--font-mono);">${dev.device_id}</strong></td>
        <td>
          <span id="name-display-${dev.device_id}">${dev.name}</span>
          <button class="btn btn-secondary btn-edit-name" data-id="${dev.device_id}" style="padding: 2px 6px; font-size: 0.7rem; margin-left: 6px;">✏️</button>
        </td>
        <td>${connBadge}</td>
        <td>${hwText}</td>
        <td style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted);">${ipText}${fwText}${wifiTag}</td>
        <td>${statusBadge}</td>
        <td><strong style="font-family: var(--font-mono); color: #FBBF24;">${dev.score} pts</strong></td>
        <td style="text-align: center;">
          <button class="btn btn-outline-teal btn-identify" data-id="${dev.device_id}" style="padding: 6px 12px; font-size: 0.8rem;">
            💡 Test LED
          </button>
        </td>
      `;

      tableBody.appendChild(row);
    });

    // Bind Edit Name Buttons
    document.querySelectorAll('.btn-edit-name').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.id;
        const currentName = document.getElementById(`name-display-${id}`).textContent;
        const newName = prompt(`Nuevo nombre para ${id}:`, currentName);
        if (newName && newName.trim() !== '') {
          updateDevice(id, newName.trim());
        }
      });
    });

    // Bind Test LED Buttons
    document.querySelectorAll('.btn-identify').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.id;
        identifyDevice(id);
      });
    });
  }

  async function identifyDevice(deviceId) {
    logTerminal(`quiz/device/${deviceId}/command`, `Comando LED "identify" enviado`);
    try {
      const res = await fetch(`/api/devices/${deviceId}/identify`, { method: 'POST' });
      const data = await res.json();
      window.soundFX.playPress();
    } catch (e) {
      console.error(e);
    }
  }

  async function updateDevice(deviceId, name) {
    try {
      const res = await fetch(`/api/devices/${deviceId}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      });
      if (res.ok) {
        const nameEl = document.getElementById(`name-display-${deviceId}`);
        if (nameEl) nameEl.textContent = name;
        logTerminal(`quiz/device/${deviceId}/update`, `Nombre actualizado a: "${name}"`);
      } else {
        alert('No se pudo actualizar el nombre.');
      }
    } catch (e) {
      console.error(e);
      alert('Error de conexión al actualizar el nombre.');
    }
  }

  // Bind MQTT Simulator: Register
  btnSimRegister.addEventListener('click', async () => {
    const hwMac = simHwMacInput.value.trim() || '84:F7:03:12:AB:91';
    const targetDevId = simTargetSelect.value;

    logTerminal('quiz/device/register', `TX Anuncio ESP32: HW=${hwMac} -> Asignar a ${targetDevId}`);
    try {
      const res = await fetch('/api/devices/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hardware_id: hwMac,
          device_id: targetDevId,
          name: `Equipo ${targetDevId} (ESP32)`,
          firmware: '1.0.2',
          ip_address: '192.168.1.105',
          connection_type: 'MQTT'
        })
      });
      const data = await res.json();
      logTerminal(`quiz/device/${hwMac}/registered`, `RX Confirmación de Servidor: Asignado exitosamente a ${data.device.device_id}`);
      window.soundFX.playStart();
    } catch (e) {
      logTerminal('quiz/error', `Error al registrar: ${e.message}`);
    }
  });

  // Bind MQTT Simulator: Button Press (A, B, C, D)
  simKeyBtns.forEach(btn => {
    btn.addEventListener('click', async () => {
      const button = btn.dataset.button;
      const targetDevId = simTargetSelect.value;

      logTerminal(`octopy/quiz/box/${targetDevId}/answer`, `TX Pulsación ESP32: Botón "${button}"`);
      window.soundFX.playPress();

      try {
        const res = await fetch('/api/answer', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            device_id: targetDevId,
            button: button
          })
        });
        const data = await res.json();
        if (data.status === 'accepted') {
          logTerminal(`octopy/quiz/box/${targetDevId}/command`, `RX Servidor: Respuesta aceptada en lugar #${data.order} (LED: Ámbar bloqueo local)`);
        } else {
          logTerminal(`octopy/quiz/box/${targetDevId}/status`, `RX Rechazado: ${data.reason}`);
        }
      } catch (err) {
        logTerminal(`octopy/quiz/box/${targetDevId}/error`, `Respuesta no aceptada: Pregunta inactiva o ya respondida`);
      }
    });
  });

  // WebSocket for Live Updates
  ws = new QuizWS('/ws/devices', (data) => {
    if (data.event === 'DEVICES_SNAPSHOT') {
      renderDevices(data.devices);
      if (data.mqtt_connected !== undefined) {
        mqttBrokerBadge.className = data.mqtt_connected ? 'badge badge-success' : 'badge badge-danger';
        mqttBrokerBadge.textContent = data.mqtt_connected 
          ? '🟢 Broker MQTT: Conectado (127.0.0.1:1883)' 
          : '🔴 Broker MQTT: Desconectado';
      }
    } else if (data.event === 'DEVICE_ANSWERED') {
      logTerminal(`quiz/device/${data.device_id}/answer`, `Respuesta procesada en Engine (Orden #${data.order})`);
    }
  });
});
