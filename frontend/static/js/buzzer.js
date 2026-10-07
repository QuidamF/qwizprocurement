/**
 * Buzzer (Mobile Controller) Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  // Extract device_id from URL query params (e.g. ?id=BOT-03)
  const urlParams = new URLSearchParams(window.location.search);
  const deviceId = (urlParams.get('id') || 'BOT-01').toUpperCase();

  // DOM Elements
  const tagDeviceId = document.getElementById('tag-device-id');
  const tagTeamName = document.getElementById('tag-team-name');
  const tagScore = document.getElementById('tag-score');

  const statusCard = document.getElementById('buzzer-status-card');
  const statusIcon = document.getElementById('status-icon');
  const statusTitle = document.getElementById('status-title');
  const statusSubtitle = document.getElementById('status-subtitle');

  const buzzerGrid = document.getElementById('buzzer-grid');
  const btnA = document.getElementById('btn-a');
  const btnB = document.getElementById('btn-b');
  const btnC = document.getElementById('btn-c');
  const btnD = document.getElementById('btn-d');
  const buttons = [btnA, btnB, btnC, btnD];

  let canAnswer = false;
  let selectedButton = null;
  let ws = null;

  tagDeviceId.textContent = deviceId;

  function setStatus(title, subtitle, icon, cardClass = '') {
    statusTitle.textContent = title;
    statusSubtitle.textContent = subtitle;
    statusIcon.textContent = icon;
    statusCard.className = 'buzzer-status-card ' + cardClass;
  }

  function handleSnapshot(snapshot) {
    if (!snapshot) return;
    const { state, device_name, score, selected_answer, order, is_correct, time_remaining } = snapshot;

    tagTeamName.textContent = device_name || `Equipo ${deviceId}`;
    tagScore.textContent = `${score || 0} pts`;

    // Reset button states
    buttons.forEach(b => b.classList.remove('selected'));

    if (state === 'ACTIVE') {
      if (selected_answer) {
        // Already answered this question
        canAnswer = false;
        buzzerGrid.className = 'buzzer-grid disabled';
        const activeBtn = document.getElementById(`btn-${selected_answer.toLowerCase()}`);
        if (activeBtn) activeBtn.classList.add('selected');
        setStatus('¡Respuesta Registrada!', `Orden de llegada: #${order}. Esperando tiempo...`, '⏳', '');
      } else {
        // Ready to answer!
        canAnswer = true;
        buzzerGrid.className = 'buzzer-grid can-answer';
        setStatus('¡ELIGE TU RESPUESTA!', `Tiempo restante: ${Math.ceil(time_remaining)}s`, '⚡', '');
      }
    } else if (state === 'TIMEOUT') {
      canAnswer = false;
      buzzerGrid.className = 'buzzer-grid disabled';
      if (selected_answer) {
        const activeBtn = document.getElementById(`btn-${selected_answer.toLowerCase()}`);
        if (activeBtn) activeBtn.classList.add('selected');
        setStatus('Tiempo Agotado', `Elegiste ${selected_answer}. Revelando respuesta...`, '🛑', '');
      } else {
        setStatus('Tiempo Agotado', 'No alcanzaste a responder', '⌛', '');
      }
    } else if (state === 'RESULT' || state === 'FINISHED') {
      canAnswer = false;
      buzzerGrid.className = 'buzzer-grid disabled';
      if (selected_answer) {
        const activeBtn = document.getElementById(`btn-${selected_answer.toLowerCase()}`);
        if (activeBtn) activeBtn.classList.add('selected');

        if (is_correct === true) {
          setStatus('¡RESPUESTA CORRECTA!', '¡Excelente! Sumaste puntos.', '🎉', 'correct');
          window.soundFX.playCorrect();
        } else if (is_correct === false) {
          setStatus('RESPUESTA INCORRECTA', '¡Mejor suerte en la siguiente!', '❌', 'incorrect');
          window.soundFX.playIncorrect();
        } else {
          setStatus('Resultado', `Elegiste ${selected_answer}`, '📊', '');
        }
      } else {
        setStatus('Pregunta Finalizada', 'Sin respuesta enviada', '⚪', '');
      }
    } else {
      // IDLE, LOBBY, QUESTION_READY
      canAnswer = false;
      buzzerGrid.className = 'buzzer-grid disabled';
      setStatus('Esperando pregunta...', 'Atento a la pantalla principal', '📡', '');
    }
  }

  function submitButton(buttonLetter) {
    if (!canAnswer) return;

    // Immediate local lock & tactile feedback
    canAnswer = false;
    selectedButton = buttonLetter;
    buzzerGrid.className = 'buzzer-grid disabled';

    const btnEl = document.getElementById(`btn-${buttonLetter.toLowerCase()}`);
    if (btnEl) btnEl.classList.add('selected');

    // Vibration on mobile device
    if (navigator.vibrate) {
      navigator.vibrate(60);
    }
    window.soundFX.playPress();

    setStatus('Enviando...', `Pulsaste ${buttonLetter}`, '⚡', '');

    // Send via WebSocket
    if (ws) {
      ws.send({ button: buttonLetter });
    }
  }

  // Bind Buttons
  buttons.forEach(btn => {
    const letter = btn.dataset.letter;
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      submitButton(letter);
    });
    btn.addEventListener('touchstart', (e) => {
      e.preventDefault();
      submitButton(letter);
    }, { passive: false });
  });

  // Enable Audio Context on tap
  document.body.addEventListener('click', () => {
    window.soundFX.init();
  }, { once: true });

  // Connect to Buzzer WebSocket
  ws = new QuizWS(`/ws/buzzer/${deviceId}`, (data) => {
    if (data.event === 'SNAPSHOT' || data.event === 'STATE_UPDATE') {
      handleSnapshot(data.snapshot);
    } else if (data.event === 'ERROR') {
      canAnswer = false;
      buzzerGrid.className = 'buzzer-grid disabled';
      const title = data.message && data.message.includes('deshabilitadas') ? 'Botoneras Web Desactivadas' : 'Conexión Rechazada';
      setStatus(title, data.message || 'Ya existe otro equipo conectado desde esta IP o el acceso web está desactivado.', '⚠️', 'error');
    } else if (data.event === 'ANSWER_ACCEPTED') {
      setStatus('¡Respuesta Registrada!', `Llegaste en orden #${data.order}`, '✅', '');
    } else if (data.event === 'TIME_UPDATE') {
      if (canAnswer) {
        statusSubtitle.textContent = `Tiempo restante: ${Math.ceil(data.time_remaining)}s`;
      }
    }
  });
});
