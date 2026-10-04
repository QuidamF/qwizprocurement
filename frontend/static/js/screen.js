/**
 * Screen (Public Game Display) Logic - With Pending Teams Tracker
 */

document.addEventListener('DOMContentLoaded', () => {
  const containerCover = document.getElementById('view-cover');
  const containerGame = document.getElementById('view-game');
  const containerLeaderboard = document.getElementById('view-leaderboard');

  const questionCounter = document.getElementById('question-counter');
  const questionLevel = document.getElementById('question-level');
  const screenStatusPill = document.getElementById('screen-status-pill');
  const questionTitle = document.getElementById('question-title');
  const optionsGrid = document.getElementById('options-grid');

  const pendingLabel = document.getElementById('pending-label');
  const pendingCountEl = document.getElementById('pending-count');
  const pendingChips = document.getElementById('pending-chips');
  const leaderboardBody = document.getElementById('leaderboard-body');

  let currentState = null;

  function formatQuestionText(text) {
    if (!text) return '';
    return text.replace(/(".*?"|[A-Z]{3,}|COMPRAS|PROVEEDOR|OBJETIVO)/g, (match) => {
      return `<span class="question-highlight">${match}</span>`;
    });
  }

  function renderState(snapshot) {
    if (!snapshot) return;
    const { state, question, current_question_index, total_questions, pending_devices, pending_count, total_devices, correct_answer, leaderboard } = snapshot;

    // View switching
    if (state === 'IDLE' || state === 'LOBBY') {
      containerCover.style.display = 'flex';
      containerGame.style.display = 'none';
      containerLeaderboard.style.display = 'none';
      updateStatusPill(state);
      return;
    } else if (state === 'FINISHED') {
      containerCover.style.display = 'none';
      containerGame.style.display = 'none';
      containerLeaderboard.style.display = 'block';
      renderLeaderboard(leaderboard);
      updateStatusPill(state);
      return;
    }

    containerCover.style.display = 'none';
    containerGame.style.display = 'flex';
    containerLeaderboard.style.display = 'none';

    // Header updates
    questionCounter.textContent = `${current_question_index} / ${total_questions || 30}`;
    if (question && question.level) {
      questionLevel.textContent = question.level.toUpperCase();
    }
    updateStatusPill(state);

    // Question & Options
    if (question) {
      questionTitle.innerHTML = formatQuestionText(question.text);
      renderOptions(question.options, state, correct_answer);
    }

    // Pending teams display
    renderPendingChips(pending_devices || [], pending_count, total_devices || 10, state);

    // Audio on state transition
    if (state !== currentState) {
      if (state === 'ACTIVE') {
        window.soundFX.playStart();
      } else if (state === 'RESULT') {
        window.soundFX.playCorrect();
      }
      currentState = state;
    }
  }

  function updateStatusPill(state) {
    screenStatusPill.className = 'badge';
    if (state === 'ACTIVE') {
      screenStatusPill.classList.add('badge-success');
      screenStatusPill.innerHTML = '<span class="pill-dot dot-success"></span> RESPUESTAS ABIERTAS';
    } else if (state === 'TIMEOUT') {
      screenStatusPill.classList.add('badge-danger');
      screenStatusPill.innerHTML = '<span class="pill-dot dot-danger"></span> TIEMPO CERRADO';
    } else if (state === 'RESULT') {
      screenStatusPill.classList.add('badge-teal');
      screenStatusPill.innerHTML = '<span class="pill-dot dot-teal"></span> RESULTADO';
    } else {
      screenStatusPill.classList.add('badge-teal');
      screenStatusPill.innerHTML = '<span class="pill-dot dot-teal"></span> ESPERANDO';
    }
  }

  function renderPendingChips(pendingList, pCount, totalCount, state) {
    pendingChips.innerHTML = '';
    const missing = (pendingList !== undefined) ? pendingList.length : pCount;

    if (totalCount === 0) {
      pendingLabel.textContent = 'Dispositivos:';
      pendingCountEl.textContent = 'Esperando conexión...';
      return;
    }

    if (missing === 0) {
      pendingLabel.textContent = '¡Todos respondieron!';
      pendingCountEl.textContent = '🎉';
      return;
    }

    pendingLabel.textContent = 'Faltan por responder:';
    pendingCountEl.textContent = `${missing} de ${totalCount}`;

    (pendingList || []).forEach(dev => {
      const chip = document.createElement('span');
      chip.className = 'team-chip';
      chip.style.borderColor = 'var(--color-danger)';
      chip.style.color = '#FCA5A5';
      chip.style.background = 'rgba(239, 68, 68, 0.2)';
      chip.textContent = dev.device_id;
      pendingChips.appendChild(chip);
    });
  }

  function renderOptions(options, state, correctAnswer) {
    optionsGrid.innerHTML = '';
    const letters = ['A', 'B', 'C', 'D'];

    letters.forEach((letter) => {
      const text = options[letter] || '';
      const card = document.createElement('div');
      card.className = 'option-card';
      card.id = `option-${letter}`;

      if (state === 'RESULT' || state === 'FINISHED') {
        if (correctAnswer && letter === correctAnswer.toUpperCase()) {
          card.classList.add('correct');
        } else {
          card.classList.add('incorrect');
        }
      }

      card.innerHTML = `
        <div class="option-badge">${letter}</div>
        <div class="option-text">${text}</div>
      `;
      optionsGrid.appendChild(card);
    });
  }

  function renderLeaderboard(leaderboard) {
    if (!leaderboardBody) return;
    leaderboardBody.innerHTML = '';

    (leaderboard || []).slice(0, 10).forEach((entry, idx) => {
      const row = document.createElement('tr');
      if (idx === 0) row.className = 'rank-1';
      else if (idx === 1) row.className = 'rank-2';
      else if (idx === 2) row.className = 'rank-3';

      const rankBadge = idx === 0 ? '👑 #1' : `#${idx + 1}`;
      row.innerHTML = `
        <td>${rankBadge}</td>
        <td><strong>${entry.device_id}</strong> - ${entry.name}</td>
        <td>${entry.score} pts</td>
      `;
      leaderboardBody.appendChild(row);
    });
  }

  // Connect WebSocket
  const ws = new QuizWS('/ws/screen', (data) => {
    if (data.event === 'SNAPSHOT' || data.event === 'STATE_UPDATE') {
      renderState(data.snapshot);
    } else if (data.event === 'ANSWER_COUNT_UPDATE') {
      renderPendingChips(data.pending_devices, data.pending_count, 10, currentState);
    }
  });

  document.body.addEventListener('click', () => {
    window.soundFX.init();
  }, { once: true });
});
