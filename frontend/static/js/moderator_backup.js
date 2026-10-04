/**
 * Simplified Moderator Console Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  let ws = null;
  let currentSnapshot = null;

  // DOM Elements
  const stateBadge = document.getElementById('mod-state-badge');
  const qProgressIndicator = document.getElementById('q-progress-indicator');
  const modSubstateText = document.getElementById('mod-substate-text');

  const btnNextQuestion = document.getElementById('btn-next-question');
  const btnCloseQuestion = document.getElementById('btn-close-question');
  const btnShowResult = document.getElementById('btn-show-result');
  const btnResetGame = document.getElementById('btn-reset-game');

  const qFilterInput = document.getElementById('q-filter');
  const questionsList = document.getElementById('questions-list');
  const activeQTitle = document.getElementById('active-q-title');
  const activeQOptions = document.getElementById('active-q-options');

  const pendingCounterText = document.getElementById('pending-counter-text');
  const totalSummaryTag = document.getElementById('total-summary-tag');
  const pendingChipsContainer = document.getElementById('pending-chips-container');
  const allDoneBanner = document.getElementById('all-done-banner');

  const answeredTableBody = document.getElementById('answered-table-body');
  const answeredCountBadge = document.getElementById('answered-count-badge');

  function sendAction(action, payload = {}) {
    if (ws) {
      ws.send({ action, ...payload });
    }
  }

  function renderModerator(snapshot) {
    if (!snapshot) return;
    currentSnapshot = snapshot;
    const { state, current_question, current_question_index, total_questions, questions_summary, answers, pending_devices, total_devices } = snapshot;

    // 1. Update State Badge & Subtext
    stateBadge.className = 'state-indicator ' + getStateClass(state);
    if (state === 'ACTIVE') {
      stateBadge.innerHTML = '🟢 ESCUCHANDO RESPUESTAS';
      modSubstateText.textContent = 'Las botoneras pueden responder ahora';
    } else if (state === 'TIMEOUT') {
      stateBadge.innerHTML = '🛑 RESPUESTAS CERRADAS';
      modSubstateText.textContent = 'Botoneras bloqueadas. Listo para revelar resultado.';
    } else if (state === 'RESULT') {
      stateBadge.innerHTML = '💡 RESULTADO MOSTRADO';
      modSubstateText.textContent = 'Respuesta revelada. Listo para siguiente pregunta.';
    } else {
      stateBadge.innerHTML = `⚪ ${state}`;
      modSubstateText.textContent = 'Listo para iniciar';
    }

    // 2. Progress Indicator
    qProgressIndicator.textContent = `Pregunta ${current_question_index + 1} / ${total_questions || 30}`;

    // 3. Action Buttons States
    // "Siguiente" is always usable to advance and auto-activate
    btnNextQuestion.disabled = false;
    // "Dejar de escuchar" is only enabled while ACTIVE
    btnCloseQuestion.disabled = (state !== 'ACTIVE');
    // "Revelar" is enabled once responses are closed (TIMEOUT) or active
    btnShowResult.disabled = (state !== 'TIMEOUT' && state !== 'ACTIVE');

    // 4. Render Active Question Box
    if (current_question) {
      activeQTitle.innerHTML = `<strong>#${current_question.id} [${current_question.level}]:</strong> ${current_question.text}`;
      activeQOptions.innerHTML = '';
      ['A', 'B', 'C', 'D'].forEach(letter => {
        const optText = current_question.options[letter] || '';
        const isCorrect = (letter === current_question.correct_answer);
        const optDiv = document.createElement('div');
        optDiv.className = 'opt-pill ' + (isCorrect ? 'correct-ans' : '');
        optDiv.innerHTML = `<strong>${letter})</strong> ${optText} ${isCorrect ? '✅ (Correcta)' : ''}`;
        activeQOptions.appendChild(optDiv);
      });
    } else {
      activeQTitle.textContent = 'Haz clic en "Siguiente Pregunta" o selecciona una de la lista';
      activeQOptions.innerHTML = '';
    }

    // 5. Render Questions List (Left panel)
    renderQuestionsList(questions_summary, current_question ? current_question.id : null);

    // 6. PRIMARY FOCUS: Render PENDING devices (Who is missing!)
    renderPendingDevices(pending_devices || [], answers ? answers.length : 0, total_devices || 10, state);

    // 7. Render Answered Devices Table
    renderAnsweredTable(answers || []);
  }

  function getStateClass(state) {
    switch (state) {
      case 'ACTIVE': return 'state-active';
      case 'TIMEOUT': return 'state-timeout';
      case 'RESULT': return 'state-result';
      default: return 'state-idle';
    }
  }

  function renderPendingDevices(pendingList, answeredCount, totalCount, state) {
    const pendingCount = pendingList.length;
    pendingCounterText.textContent = `Faltan por responder: ${pendingCount} de ${totalCount} equipos`;
    totalSummaryTag.textContent = `${answeredCount} / ${totalCount} respondieron`;
    answeredCountBadge.textContent = answeredCount;

    pendingChipsContainer.innerHTML = '';

    if (pendingCount === 0 && answeredCount > 0) {
      allDoneBanner.style.display = 'flex';
      pendingChipsContainer.style.display = 'none';
      return;
    }

    allDoneBanner.style.display = 'none';
    pendingChipsContainer.style.display = 'flex';

    if (state !== 'ACTIVE' && answeredCount === 0) {
      pendingCounterText.textContent = `Equipos listos: ${totalCount}`;
    }

    pendingList.forEach(dev => {
      const badge = document.createElement('div');
      badge.className = 'pending-team-badge';
      badge.innerHTML = `<span>⏳</span> <strong>${dev.device_id}</strong> (${dev.name})`;
      pendingChipsContainer.appendChild(badge);
    });
  }

  function renderAnsweredTable(answers) {
    answeredTableBody.innerHTML = '';
    if (!answers || answers.length === 0) {
      answeredTableBody.innerHTML = `
        <tr>
          <td colspan="4" style="text-align: center; color: var(--text-dim); padding: 14px;">
            Ninguna respuesta recibida aún
          </td>
        </tr>
      `;
      return;
    }

    answers.forEach(ans => {
      const row = document.createElement('tr');
      let statusStyle = '';
      if (ans.is_correct === true) statusStyle = 'color: var(--color-success); font-weight: bold;';
      else if (ans.is_correct === false) statusStyle = 'color: var(--color-danger);';

      row.innerHTML = `
        <td><strong style="color: var(--accent-teal);">#${ans.order}</strong></td>
        <td><strong>${ans.device_id}</strong> <span style="font-size: 0.8rem; color: var(--text-muted);">(${ans.device_name})</span></td>
        <td><span class="badge badge-teal">${ans.answer}</span></td>
        <td style="${statusStyle}">
          ${ans.points ? `+${ans.points} pts` : (ans.is_correct === false ? '0 pts' : '—')}
        </td>
      `;
      answeredTableBody.appendChild(row);
    });
  }

  function renderQuestionsList(questions, selectedId) {
    if (!questions) return;
    const filterText = (qFilterInput.value || '').toLowerCase();
    questionsList.innerHTML = '';

    questions.forEach(q => {
      if (filterText && !q.text.toLowerCase().includes(filterText) && !q.level.toLowerCase().includes(filterText)) {
        return;
      }

      const item = document.createElement('div');
      item.className = 'question-list-item ' + (q.id === selectedId ? 'selected' : '');
      item.innerHTML = `
        <div class="q-item-num">#${q.id} - ${q.level.toUpperCase()}</div>
        <div class="q-item-text">${q.text}</div>
      `;
      // Clicking a question activates it automatically!
      item.addEventListener('click', () => {
        sendAction('select_question', { question_id: q.id });
      });
      questionsList.appendChild(item);
    });
  }

  // Bind Buttons
  btnNextQuestion.addEventListener('click', () => {
    sendAction('next_question');
  });

  btnCloseQuestion.addEventListener('click', () => {
    sendAction('close_question');
  });

  btnShowResult.addEventListener('click', () => {
    sendAction('show_result');
  });

  btnResetGame.addEventListener('click', () => {
    if (confirm('¿Reiniciar la partida y puntuaciones al inicio?')) {
      sendAction('reset_game');
    }
  });

  qFilterInput.addEventListener('input', () => {
    if (currentSnapshot) {
      renderQuestionsList(
        currentSnapshot.questions_summary,
        currentSnapshot.current_question ? currentSnapshot.current_question.id : null
      );
    }
  });

  // Connect WebSocket
  ws = new QuizWS('/ws/moderator', (data) => {
    if (data.event === 'SNAPSHOT' || data.event === 'STATE_UPDATE') {
      renderModerator(data.snapshot);
    } else if (data.event === 'ANSWER_RECEIVED') {
      if (currentSnapshot) {
        currentSnapshot.answers.push(data.submission);
        currentSnapshot.pending_devices = data.pending_devices || [];
        renderPendingDevices(
          currentSnapshot.pending_devices,
          currentSnapshot.answers.length,
          currentSnapshot.total_devices || 10,
          currentSnapshot.state
        );
        renderAnsweredTable(currentSnapshot.answers);
      }
    }
  });
});
