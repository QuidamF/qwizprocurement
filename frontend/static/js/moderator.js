/**
 * ============================================================================
 * OCTOPY QUIZ - CABINA DE CONTROL DEL MODERADOR (TV BROADCAST SUITE)
 * ============================================================================
 */

document.addEventListener('DOMContentLoaded', () => {
  let ws = null;
  let currentSnapshot = null;

  // DOM Elements - Header & State
  const stateBadge = document.getElementById('mod-state-badge');
  const stateText = document.getElementById('state-text');
  const qProgressIndicator = document.getElementById('q-progress-indicator');
  const modSubstateText = document.getElementById('mod-substate-text');

  // DOM Elements - TV Action Controls
  const btnNextQuestion = document.getElementById('btn-next-question');
  const btnNextBadge = document.getElementById('btn-next-badge');
  const btnNextIcon = document.getElementById('btn-next-icon');
  const btnNextTitle = document.getElementById('btn-next-title');
  const btnNextSub = document.getElementById('btn-next-sub');
  const btnCloseQuestion = document.getElementById('btn-close-question');
  const btnShowResult = document.getElementById('btn-show-result');
  const btnResetGame = document.getElementById('btn-reset-game');

  // DOM Elements - Sidebar & Search
  const modSidebar = document.getElementById('mod-sidebar');
  const btnToggleSidebar = document.getElementById('btn-toggle-sidebar');
  const qFilterInput = document.getElementById('q-filter');
  const questionsList = document.getElementById('questions-list');

  // DOM Elements - Active Question
  const activeQLevel = document.getElementById('active-q-level');
  const activeQTitle = document.getElementById('active-q-title');
  const activeQOptions = document.getElementById('active-q-options');

  // DOM Elements - Missing / Pending Teams Monitor
  const pendingCounterText = document.getElementById('pending-counter-text');
  const totalSummaryTag = document.getElementById('total-summary-tag');
  const pendingChipsContainer = document.getElementById('pending-chips-container');
  const allDoneBanner = document.getElementById('all-done-banner');

  // DOM Elements - Arrivals Table
  const answeredTableBody = document.getElementById('answered-table-body');
  const answeredCountBadge = document.getElementById('answered-count-badge');

  // DOM Elements - Shortcuts Modal
  const modalShortcuts = document.getElementById('modal-shortcuts');
  const btnShowShortcuts = document.getElementById('btn-show-shortcuts');
  const btnCloseModal = document.getElementById('btn-close-modal');

  // -------------------------------------------------------------------------
  // WebSocket Action Sender
  // -------------------------------------------------------------------------
  function sendAction(action, payload = {}) {
    if (ws) {
      ws.send({ action, ...payload });
    }
  }

  // -------------------------------------------------------------------------
  // Main Render State
  // -------------------------------------------------------------------------
  function renderModerator(snapshot) {
    if (!snapshot) return;
    currentSnapshot = snapshot;
    const { 
      state, 
      current_question, 
      current_question_index, 
      total_questions, 
      questions_summary, 
      answers, 
      pending_devices, 
      total_devices 
    } = snapshot;

    // 1. Update State Badge & Subtitle
    stateBadge.className = 'state-pill ' + getStateClass(state);
    if (state === 'ACTIVE') {
      stateText.textContent = 'EN VIVO • ESCUCHANDO';
      modSubstateText.textContent = 'Botoneras desbloqueadas. Esperando pulsaciones...';
    } else if (state === 'TIMEOUT') {
      stateText.textContent = 'RESPUESTAS CERRADAS';
      modSubstateText.textContent = 'Botoneras bloqueadas. Listo para revelar la respuesta ganadora.';
    } else if (state === 'RESULT') {
      stateText.textContent = 'RESULTADO MOSTRADO';
      modSubstateText.textContent = 'Puntajes asignados. Listo para avanzar a la siguiente pregunta.';
    } else {
      stateText.textContent = state;
      modSubstateText.textContent = 'Listo para iniciar';
    }

    // 2. Progress Indicator
    const isGameWaiting = (!current_question || current_question_index === undefined || current_question_index < 0 || state === 'IDLE');
    if (isGameWaiting) {
      qProgressIndicator.textContent = `En espera (0 / ${total_questions || 30})`;
    } else {
      qProgressIndicator.textContent = `Pregunta ${current_question_index + 1} / ${total_questions || 30}`;
    }

    // 3. Action Buttons Ergonomics
    btnNextQuestion.disabled = false;
    btnCloseQuestion.disabled = (state !== 'ACTIVE');
    btnShowResult.disabled = (state !== 'TIMEOUT' && state !== 'ACTIVE');

    // Adapt Button 1: Iniciar Trivia vs Siguiente Pregunta
    if (isGameWaiting) {
      btnNextQuestion.classList.add('tv-btn-start');
      if (btnNextBadge) btnNextBadge.textContent = 'INICIAR TRIVIA • [Espacio]';
      if (btnNextIcon) btnNextIcon.textContent = '🚀';
      if (btnNextTitle) btnNextTitle.textContent = 'Iniciar Trivia';
      if (btnNextSub) btnNextSub.textContent = 'Arranca con la Pregunta 1';
      btnNextQuestion.setAttribute('title', 'Atajo: [Espacio] - Iniciar Trivia (Pregunta 1)');
    } else {
      btnNextQuestion.classList.remove('tv-btn-start');
      if (btnNextBadge) btnNextBadge.textContent = 'PASO 1 • [Espacio] o [N]';
      if (btnNextIcon) btnNextIcon.textContent = '⏭️';
      if (btnNextTitle) btnNextTitle.textContent = 'Siguiente Pregunta';
      if (btnNextSub) btnNextSub.textContent = 'Avanza y activa respuestas';
      btnNextQuestion.setAttribute('title', 'Atajo: [Espacio] o [N] - Siguiente Pregunta');
    }

    // 4. Render Active Question Presenter
    if (current_question) {
      activeQLevel.textContent = `NIVEL: ${current_question.level ? current_question.level.toUpperCase() : 'GENERAL'}`;
      activeQTitle.textContent = `#${current_question.id}. ${current_question.text}`;
      activeQOptions.innerHTML = '';

      ['A', 'B', 'C', 'D'].forEach(letter => {
        const optText = current_question.options[letter] || '';
        const isCorrect = (letter === current_question.correct_answer);

        const card = document.createElement('div');
        card.className = `tv-opt-card ${isCorrect ? 'correct' : ''}`;
        card.innerHTML = `
          <span class="tv-opt-letter">${letter}</span>
          <span style="font-weight: 600;">${optText}</span>
        `;
        activeQOptions.appendChild(card);
      });
    } else {
      activeQLevel.textContent = 'EN ESPERA';
      activeQTitle.innerHTML = 'Presiona <span style="color: #34D399; font-weight: 800;">"Iniciar Trivia"</span> para arrancar con la Pregunta 1';
      activeQOptions.innerHTML = '';
    }

    // 5. Render Questions Playlist (Sidebar)
    renderQuestionsPlaylist(questions_summary, current_question ? current_question.id : null);

    // 6. PRIMARY FOCUS: Missing / Pending Teams Monitor
    renderPendingMonitor(pending_devices || [], answers ? answers.length : 0, total_devices || 10, state);

    // 7. Arrival Feed & Scoreboard Table
    renderArrivalTable(answers || []);
  }

  function getStateClass(state) {
    switch (state) {
      case 'ACTIVE': return 'state-active';
      case 'TIMEOUT': return 'state-timeout';
      case 'RESULT': return 'state-result';
      default: return 'state-idle';
    }
  }

  // -------------------------------------------------------------------------
  // Render Pending Teams Monitor
  // -------------------------------------------------------------------------
  function renderPendingMonitor(pendingList, answeredCount, totalCount, state) {
    const pendingCount = pendingList.length;
    answeredCountBadge.textContent = answeredCount;

    if (totalCount === 0) {
      pendingCounterText.textContent = `Sin dispositivos conectados (Esperando ESP32 MQTT o Web)`;
      totalSummaryTag.textContent = `0 equipos`;
      allDoneBanner.style.display = 'none';
      pendingChipsContainer.style.display = 'flex';
      pendingChipsContainer.innerHTML = `
        <div style="color: var(--text-muted); font-size: 0.85rem; padding: 12px; display: flex; align-items: center; gap: 8px;">
          <span class="live-indicator-dot" style="background: var(--accent-amber); box-shadow: 0 0 8px var(--accent-amber);"></span>
          Esperando que los dispositivos se conecten a la red en tiempo real...
        </div>`;
      return;
    }

    if (state !== 'ACTIVE' && answeredCount === 0) {
      pendingCounterText.textContent = `Equipos conectados en sala: ${totalCount}`;
    } else {
      pendingCounterText.textContent = `Faltan por responder: ${pendingCount} de ${totalCount} equipos`;
    }

    totalSummaryTag.textContent = `${answeredCount} / ${totalCount} respondieron`;
    pendingChipsContainer.innerHTML = '';

    if (pendingCount === 0 && answeredCount > 0) {
      allDoneBanner.style.display = 'flex';
      pendingChipsContainer.style.display = 'none';
      return;
    }

    allDoneBanner.style.display = 'none';
    pendingChipsContainer.style.display = 'flex';

    pendingList.forEach(dev => {
      const chip = document.createElement('div');
      chip.className = 'pending-team-chip';
      const icon = dev.connection_type === 'MQTT' ? '📡' : '🌐';
      const ipBadge = dev.ip_address ? ` <span style="opacity: 0.65; font-size: 0.72rem;">[${dev.ip_address}]</span>` : '';
      chip.innerHTML = `
        <span>${icon}</span> 
        <strong>${dev.device_id}</strong> 
        <span style="opacity: 0.85; font-size: 0.78rem;">(${dev.name})</span>${ipBadge}
        <button class="btn-chip-rename" data-id="${dev.device_id}" data-name="${dev.name}" title="Cambiar nombre de equipo" style="background: none; border: none; cursor: pointer; font-size: 0.75rem; padding: 2px 4px; color: var(--accent-teal); opacity: 0.75; transition: opacity 0.15s;" onmouseover="this.style.opacity='1'" onmouseout="this.style.opacity='0.75'">✏️</button>
      `;
      pendingChipsContainer.appendChild(chip);
    });
  }

  // -------------------------------------------------------------------------
  // Render Arrival Table (Feed en Vivo)
  // -------------------------------------------------------------------------
  function renderArrivalTable(answers) {
    answeredTableBody.innerHTML = '';
    if (!answers || answers.length === 0) {
      answeredTableBody.innerHTML = `
        <tr>
          <td colspan="5" class="empty-state-cell">
            Esperando que los equipos presionen sus botoneras...
          </td>
        </tr>
      `;
      return;
    }

    answers.forEach((ans, idx) => {
      const row = document.createElement('tr');
      const order = ans.order || (idx + 1);

      // Pos badge styling
      let posClass = 'pos-other';
      if (order === 1) posClass = 'pos-1';
      else if (order === 2) posClass = 'pos-2';
      else if (order === 3) posClass = 'pos-3';

      // Reaction time formatting
      let reactionStr = '—';
      if (ans.reaction_ms) {
        reactionStr = (ans.reaction_ms < 1000) 
          ? `${ans.reaction_ms}ms` 
          : `${(ans.reaction_ms / 1000).toFixed(2)}s`;
      }

      // Points & Correctness styling
      let pointsCell = '<span style="color: var(--text-dim);">En espera...</span>';
      if (ans.is_correct === true) {
        pointsCell = `<strong style="color: #34D399;">+${ans.points || 100} pts</strong>`;
      } else if (ans.is_correct === false) {
        pointsCell = `<span style="color: #F87171;">0 pts (Fallo)</span>`;
      }

      row.innerHTML = `
        <td><span class="pos-tag ${posClass}">${order}º</span></td>
        <td>
          <strong>${ans.device_id}</strong> 
          <span style="font-size: 0.8rem; color: var(--text-muted);">(${ans.device_name})</span>
          <button class="btn-chip-rename" data-id="${ans.device_id}" data-name="${ans.device_name}" title="Cambiar nombre de equipo" style="background: none; border: none; cursor: pointer; font-size: 0.75rem; padding: 2px 4px; color: var(--accent-teal); opacity: 0.75; transition: opacity 0.15s;" onmouseover="this.style.opacity='1'" onmouseout="this.style.opacity='0.75'">✏️</button>
        </td>
        <td><span class="reaction-pill">⚡ ${reactionStr}</span></td>
        <td><span class="ans-badge">${ans.answer}</span></td>
        <td style="text-align: right;">${pointsCell}</td>
      `;
      answeredTableBody.appendChild(row);
    });
  }

  // -------------------------------------------------------------------------
  // Render Questions Playlist (Sidebar)
  // -------------------------------------------------------------------------
  function renderQuestionsPlaylist(questions, selectedId) {
    if (!questions) return;
    const filter = (qFilterInput.value || '').toLowerCase().trim();
    questionsList.innerHTML = '';

    questions.forEach(q => {
      if (filter && !q.text.toLowerCase().includes(filter) && !q.level.toLowerCase().includes(filter)) {
        return;
      }

      const card = document.createElement('div');
      card.className = `q-playlist-card ${q.id === selectedId ? 'selected' : ''}`;
      card.innerHTML = `
        <div class="q-playlist-num">#${q.id} • ${q.level.toUpperCase()}</div>
        <div class="q-playlist-text">${q.text}</div>
      `;

      card.addEventListener('click', () => {
        sendAction('select_question', { question_id: q.id });
        closeSidebar();
      });

      questionsList.appendChild(card);
    });
  }

  // -------------------------------------------------------------------------
  // TV & Tablet Actions Bindings
  // -------------------------------------------------------------------------
  function triggerButtonAction(btn, action) {
    if (btn && !btn.disabled) {
      btn.style.transform = 'scale(0.96)';
      setTimeout(() => { btn.style.transform = ''; }, 120);
      sendAction(action);
    }
  }

  btnNextQuestion.addEventListener('click', () => {
    const isGameWaiting = (!currentSnapshot || !currentSnapshot.current_question || currentSnapshot.state === 'IDLE');
    if (isGameWaiting) {
      triggerButtonAction(btnNextQuestion, 'start_game');
    } else {
      triggerButtonAction(btnNextQuestion, 'next_question');
    }
  });

  btnCloseQuestion.addEventListener('click', () => {
    triggerButtonAction(btnCloseQuestion, 'close_question');
  });

  btnShowResult.addEventListener('click', () => {
    triggerButtonAction(btnShowResult, 'show_result');
  });

  btnResetGame.addEventListener('click', () => {
    if (confirm('¿Reiniciar la partida y puntuaciones al inicio?')) {
      sendAction('reset_game');
    }
  });

  // Edit Team Name from Moderator UI
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.btn-chip-rename');
    if (btn) {
      e.stopPropagation();
      const id = btn.dataset.id;
      const currentName = btn.dataset.name || id;
      const newName = prompt(`Cambiar nombre para ${id}:`, currentName);
      if (newName && newName.trim() !== '' && newName.trim() !== currentName) {
        try {
          const res = await fetch(`/api/devices/${id}/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName.trim() })
          });
          if (!res.ok) {
            alert('Error al actualizar el nombre del equipo.');
          }
        } catch (err) {
          console.error(err);
          alert('Error de conexión al actualizar el nombre.');
        }
      }
    }
  });

  // Universal Fullscreen & Webkit & CSS Fallback for Tablets / iPads
  const btnFullscreen = document.getElementById('btn-fullscreen');

  function isCurrentlyFullscreen() {
    return !!(
      document.fullscreenElement ||
      document.webkitFullscreenElement ||
      document.mozFullScreenElement ||
      document.msFullscreenElement ||
      document.body.classList.contains('fullscreen-mode')
    );
  }

  function updateFullscreenButton(isFS) {
    if (!btnFullscreen) return;
    if (isFS) {
      btnFullscreen.innerHTML = '🗗 <span class="hide-mobile">Salir Fullscreen</span>';
    } else {
      btnFullscreen.innerHTML = '⛶ <span class="hide-mobile">Pantalla Completa</span>';
    }
  }

  function toggleFullscreen() {
    const elem = document.documentElement;
    const isFS = isCurrentlyFullscreen();

    if (!isFS) {
      let promise = null;
      if (elem.requestFullscreen) {
        promise = elem.requestFullscreen();
      } else if (elem.webkitRequestFullscreen) {
        promise = elem.webkitRequestFullscreen();
      } else if (elem.mozRequestFullScreen) {
        promise = elem.mozRequestFullScreen();
      } else if (elem.msRequestFullscreen) {
        promise = elem.msRequestFullscreen();
      }

      if (promise && promise.catch) {
        promise.then(() => updateFullscreenButton(true)).catch(() => {
          // If browser rejects (e.g. iPad Safari without user permission), use CSS Fullscreen
          document.body.classList.add('fullscreen-mode');
          updateFullscreenButton(true);
        });
      } else {
        // Native API not available (iPadOS Safari) -> CSS Fullscreen
        document.body.classList.add('fullscreen-mode');
        updateFullscreenButton(true);
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
      } else if (document.mozCancelFullScreen) {
        document.mozCancelFullScreen();
      } else if (document.msExitFullscreen) {
        document.msExitFullscreen();
      }
      document.body.classList.remove('fullscreen-mode');
      updateFullscreenButton(false);
    }
  }

  if (btnFullscreen) {
    btnFullscreen.addEventListener('click', toggleFullscreen);

    ['fullscreenchange', 'webkitfullscreenchange', 'mozfullscreenchange', 'MSFullscreenChange'].forEach(evt => {
      document.addEventListener(evt, () => {
        const isFS = isCurrentlyFullscreen();
        updateFullscreenButton(isFS);
        if (!isFS) {
          document.body.classList.remove('fullscreen-mode');
        }
      });
    });
  }

  // Off-Canvas Sidebar Drawer Controls
  const sidebarBackdrop = document.getElementById('sidebar-backdrop');
  const btnCloseSidebar = document.getElementById('btn-close-sidebar');

  function openSidebar() {
    modSidebar.classList.add('open');
    if (sidebarBackdrop) sidebarBackdrop.classList.add('active');
  }

  function closeSidebar() {
    modSidebar.classList.remove('open');
    if (sidebarBackdrop) sidebarBackdrop.classList.remove('active');
  }

  btnToggleSidebar.addEventListener('click', () => {
    if (modSidebar.classList.contains('open')) {
      closeSidebar();
    } else {
      openSidebar();
    }
  });

  if (sidebarBackdrop) sidebarBackdrop.addEventListener('click', closeSidebar);
  if (btnCloseSidebar) btnCloseSidebar.addEventListener('click', closeSidebar);

  // Search filter
  qFilterInput.addEventListener('input', () => {
    if (currentSnapshot) {
      renderQuestionsPlaylist(
        currentSnapshot.questions_summary,
        currentSnapshot.current_question ? currentSnapshot.current_question.id : null
      );
    }
  });

  // -------------------------------------------------------------------------
  // Keyboard Shortcuts (Cabina de TV)
  // -------------------------------------------------------------------------
  document.addEventListener('keydown', (e) => {
    // Si el usuario está escribiendo en el buscador de preguntas, no interferir
    if (document.activeElement === qFilterInput) {
      return;
    }

    const key = e.key.toLowerCase();

    // 1. Iniciar Trivia / Siguiente Pregunta: [Espacio] o [N]
    if (e.code === 'Space' || key === 'n') {
      e.preventDefault();
      const isGameWaiting = (!currentSnapshot || !currentSnapshot.current_question || currentSnapshot.state === 'IDLE');
      if (isGameWaiting) {
        triggerButtonAction(btnNextQuestion, 'start_game');
      } else {
        triggerButtonAction(btnNextQuestion, 'next_question');
      }
    }
    // 2. Dejar de Escuchar: [Enter] o [S]
    else if (e.code === 'Enter' || key === 's') {
      e.preventDefault();
      if (!btnCloseQuestion.disabled) {
        triggerButtonAction(btnCloseQuestion, 'close_question');
      }
    }
    // 3. Revelar Resultado: [R]
    else if (key === 'r') {
      e.preventDefault();
      if (!btnShowResult.disabled) {
        triggerButtonAction(btnShowResult, 'show_result');
      }
    }
    // 4. Modal de atajos: [?]
    else if (key === '?' || e.key === '?') {
      toggleShortcutsModal();
    }
    // 5. Esc: Cerrar modal o confirmación reset
    else if (e.code === 'Escape') {
      if (modalShortcuts.style.display !== 'none') {
        modalShortcuts.style.display = 'none';
      }
    }
  });

  function toggleShortcutsModal() {
    const isVisible = (modalShortcuts.style.display !== 'none');
    modalShortcuts.style.display = isVisible ? 'none' : 'flex';
  }

  btnShowShortcuts.addEventListener('click', toggleShortcutsModal);
  btnCloseModal.addEventListener('click', () => {
    modalShortcuts.style.display = 'none';
  });

  modalShortcuts.addEventListener('click', (e) => {
    if (e.target === modalShortcuts) {
      modalShortcuts.style.display = 'none';
    }
  });

  // -------------------------------------------------------------------------
  // WebSocket Connection
  // -------------------------------------------------------------------------
  ws = new QuizWS('/ws/moderator', (data) => {
    if (data.event === 'SNAPSHOT' || data.event === 'STATE_UPDATE') {
      renderModerator(data.snapshot);
    } else if (data.event === 'ANSWER_RECEIVED') {
      if (currentSnapshot) {
        currentSnapshot.answers.push(data.submission);
        currentSnapshot.pending_devices = data.pending_devices || [];
        renderPendingMonitor(
          currentSnapshot.pending_devices,
          currentSnapshot.answers.length,
          currentSnapshot.total_devices || 10,
          currentSnapshot.state
        );
        renderArrivalTable(currentSnapshot.answers);
      }
    }
  });
});
