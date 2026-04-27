(function(){
  const trigger = document.getElementById("pokerLeftiesTrigger");
  const root = document.querySelector("[data-poker-lefties]");
  const modalEl = document.getElementById("pokerLeftiesModal");
  if (!trigger || !root || !modalEl || !window.bootstrap) return;

  const modal = new bootstrap.Modal(modalEl);
  const csrf = root.dataset.csrf;
  const cardsEl = document.getElementById("pokerCards");
  const msgEl = document.getElementById("pokerMessage");
  const resultEl = document.getElementById("pokerResult");
  const pointsEl = document.getElementById("pokerPoints");
  const handsEl = document.getElementById("pokerHands");
  const streakEl = document.getElementById("pokerStreak");
  const resetEl = document.getElementById("pokerReset");
  const extraEl = document.getElementById("pokerExtra");
  const roundEl = document.getElementById("pokerRound");
  const historyEl = document.getElementById("pokerHistory");
  const jokersEl = document.getElementById("pokerJokers");
  const achievementsEl = document.getElementById("pokerAchievements");
  const rankingEl = document.getElementById("pokerRanking");
  const startBtn = document.getElementById("pokerStart");
  const discardBtn = document.getElementById("pokerDiscard");
  const keepBtn = document.getElementById("pokerKeep");
  const scoreBtn = document.getElementById("pokerScore");
  let clickCount = 0;

  function api(path, options) {
    const opts = options || {};
    opts.headers = Object.assign({"X-CSRFToken": csrf, "Content-Type": "application/json"}, opts.headers || {});
    return fetch(path, opts).then(r => r.json());
  }

  function setMessage(text, error) {
    msgEl.textContent = text || "";
    msgEl.classList.toggle("is-error", Boolean(error));
  }

  function renderRound(round, canScore) {
    const current = Math.min(Number(round || 0) + (canScore ? 0 : 1), 3);
    roundEl.textContent = canScore ? "Vuelta de descarte 3/3 completa" : `Vuelta de descarte ${current}/3`;
  }

  function renderStatus(status) {
    if (!status) return;
    pointsEl.textContent = status.points_total;
    handsEl.textContent = `${status.total_hands_remaining}/${status.hands_limit}`;
    streakEl.textContent = `${status.streak_current}/${status.streak_best}`;
    resetEl.textContent = status.resets_at || "-";
    extraEl.textContent = `Manos: ${status.base_hands_remaining} normales + ${status.extra_hands_remaining} extra`;
    if (status.extra_hand_grants && status.extra_hand_grants.length) {
      extraEl.textContent += " · " + status.extra_hand_grants.map(g => `+${g.remaining} por ${g.source}`).join(" · ");
    }
    startBtn.disabled = !status.enabled || status.total_hands_remaining <= 0;
    renderJokers(status.jokers);
    renderAchievements(status.achievements);
  }

  function suitClass(card) {
    return card.suit === "H" || card.suit === "D" ? "is-red" : "is-black";
  }

  function renderCards(cards, selectable) {
    cardsEl.innerHTML = "";
    if (!cards || !cards.length) {
      cardsEl.innerHTML = '<div class="poker16-empty">Esperando mano...</div>';
      return;
    }
    cards.forEach(card => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "poker16-card pixel-card " + suitClass(card);
      button.dataset.cardId = card.id;
      button.disabled = !selectable;
      button.innerHTML = `<span class="corner top">${card.rank}</span><strong>${card.symbol}</strong><span class="corner bottom">${card.rank}</span>`;
      button.addEventListener("click", () => button.classList.toggle("selected"));
      cardsEl.appendChild(button);
    });
  }

  function selectedIds() {
    return Array.from(cardsEl.querySelectorAll(".poker16-card.selected")).map(card => card.dataset.cardId);
  }

  function renderResult(result, unlockedAchievements, unlockedJokers) {
    if (!result) {
      resultEl.innerHTML = "";
      return;
    }
    const bonuses = (result.bonuses || []).map(b => `<li><strong>+${b.points}</strong> ${b.name} — ${b.description}</li>`).join("");
    const multipliers = (result.multipliers || []).map(m => `<li><strong>x${m.multiplier}</strong> ${m.name} — ${m.description}</li>`).join("");
    const achievements = (unlockedAchievements || []).map(a => `<span class="pixel-badge">Logro desbloqueado: ${a.name}</span>`).join("");
    const jokers = (unlockedJokers || []).map(j => `<span class="pixel-badge">Nuevo comodín desbloqueado: ${j.name}</span>`).join("");
    resultEl.innerHTML = `
      <div class="poker16-score-card">
        <strong>Jugada: ${result.result_name || result.name}</strong>
        <em>Puntaje base: ${result.base_score}</em>
        <div class="poker16-score-columns">
          <div><b>Bonos aplicados</b><ul>${bonuses || "<li>Sin bonos aplicados.</li>"}</ul></div>
          <div><b>Multiplicadores</b><ul>${multipliers || "<li>x1.00 sin multiplicadores.</li>"}</ul></div>
        </div>
        <div class="poker16-total">Racha: +${result.streak_bonus || 0} · Total: ${result.final_score || result.score}</div>
        <div class="poker16-bonus-list">${achievements}${jokers}</div>
      </div>`;
  }

  function renderHistory(hands) {
    historyEl.innerHTML = "";
    if (!hands || hands.length === 0) {
      historyEl.innerHTML = '<div class="poker16-empty">Todavía no hay manos jugadas.</div>';
      return;
    }
    hands.forEach(hand => {
      const row = document.createElement("div");
      row.className = "poker16-history-row";
      row.innerHTML = `<span>${hand.played_at}</span><strong>${hand.result_name}</strong><em>+${hand.final_score || hand.score}</em>`;
      historyEl.appendChild(row);
    });
  }

  function jokerCard(joker, controls) {
    return `<div class="poker16-joker ${joker.state || ""}">
      <strong>${joker.name}</strong>
      <p>${joker.effect || joker.description}</p>
      <small>${joker.state === "locked" ? "Bloqueado: " + joker.unlock_rule : joker.equipped_slot ? "Equipado slot " + joker.equipped_slot : "Desbloqueado"}</small>
      ${controls ? `<div><button type="button" data-joker-code="${joker.code}" data-joker-slot="1">S1</button><button type="button" data-joker-code="${joker.code}" data-joker-slot="2">S2</button>${joker.equipped_slot ? `<button type="button" data-joker-unequip="${joker.code}">OFF</button>` : ""}</div>` : ""}
    </div>`;
  }

  function renderJokers(jokers) {
    if (!jokers) return;
    jokersEl.innerHTML = `
      <div class="poker16-joker-section"><div class="poker16-panel-title">Equipados</div>${(jokers.equipped || []).map(j => jokerCard(j, true)).join("") || '<div class="poker16-empty">Sin comodines equipados.</div>'}</div>
      <div class="poker16-joker-section"><div class="poker16-panel-title">Desbloqueados disponibles</div>${(jokers.unlocked || []).map(j => jokerCard(j, true)).join("") || '<div class="poker16-empty">No hay comodines libres.</div>'}</div>
      <div class="poker16-joker-section"><div class="poker16-panel-title">Bloqueados</div>${(jokers.locked || []).map(j => jokerCard(j, false)).join("") || '<div class="poker16-empty">Todos desbloqueados.</div>'}</div>`;
  }

  function renderAchievements(data) {
    achievementsEl.innerHTML = "";
    const unlocked = data && data.unlocked ? data.unlocked : [];
    const locked = data && data.locked ? data.locked : [];
    achievementsEl.innerHTML = `
      <div class="poker16-joker-section"><div class="poker16-panel-title">Logros desbloqueados</div>${unlocked.map(a => `<div class="poker16-achievement"><strong>${a.name}</strong><span>${a.description}</span><small>${a.unlocked_at} / +${a.points_reward}</small></div>`).join("") || '<div class="poker16-empty">Sin logros todavía.</div>'}</div>
      <div class="poker16-joker-section"><div class="poker16-panel-title">Pendientes</div>${locked.map(a => `<div class="poker16-achievement locked"><strong>${a.name}</strong><span>${a.description}</span><small>Pendiente</small></div>`).join("")}</div>`;
  }

  function renderRanking(data) {
    if (!data || !data.enabled) {
      rankingEl.innerHTML = '<div class="poker16-empty">Ranking deshabilitado para este usuario.</div>';
      return;
    }
    const sections = [
      ["Puntos totales", data.ranking.points, row => row.value],
      ["Mejor mano", data.ranking.best_hand, row => `${row.value} ${row.result || ""}`],
      ["Racha", data.ranking.streak, row => row.value]
    ];
    rankingEl.innerHTML = sections.map(([title, rows, valueFn]) => `
      <div class="poker16-rank-panel">
        <strong>${title}</strong>
        ${(rows || []).map((row, index) => `<div><span>${index + 1}. ${row.name} / ${row.area}</span><em>${valueFn(row)}</em></div>`).join("") || '<small>Sin datos.</small>'}
      </div>`).join("");
  }

  function loadHistory() { return api("/game/history", {method: "GET"}).then(data => renderHistory(data.hands)); }
  function loadRanking() { return api("/game/ranking", {method: "GET"}).then(renderRanking); }

  function loadStatus() {
    return api("/game/status", {method: "GET"}).then(data => {
      renderStatus(data.status);
      if (data.active_hand) {
        const round = data.active_hand.discard_round || 0;
        const canScore = round >= 3;
        renderRound(round, canScore);
        renderCards(data.active_hand.final || data.active_hand.dealt, !canScore);
        discardBtn.disabled = canScore;
        keepBtn.disabled = canScore;
        scoreBtn.disabled = !canScore;
      } else {
        renderRound(0, false);
        renderCards([], false);
        discardBtn.disabled = true;
        keepBtn.disabled = true;
        scoreBtn.disabled = true;
      }
      if (!data.status.enabled) setMessage("Juego deshabilitado para tu usuario.", true);
      return data;
    });
  }

  document.querySelectorAll("[data-poker-tab]").forEach(button => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-poker-tab]").forEach(btn => btn.classList.toggle("active", btn === button));
      document.querySelectorAll("[data-poker-panel]").forEach(panel => panel.classList.toggle("active", panel.dataset.pokerPanel === button.dataset.pokerTab));
      if (button.dataset.pokerTab === "ranking") loadRanking();
    });
  });

  jokersEl.addEventListener("click", event => {
    const unequip = event.target.closest("[data-joker-unequip]");
    const equip = event.target.closest("[data-joker-code]");
    if (unequip) {
      api("/game/unequip-joker", {method: "POST", body: JSON.stringify({code: unequip.dataset.jokerUnequip})}).then(data => {
        if (!data.ok) return setMessage(data.error, true);
        renderStatus(data.status);
        setMessage("Comodín quitado.", false);
      });
      return;
    }
    if (!equip) return;
    api("/game/equip-joker", {method: "POST", body: JSON.stringify({code: equip.dataset.jokerCode, slot: equip.dataset.jokerSlot})}).then(data => {
      if (!data.ok) return setMessage(data.error, true);
      renderStatus(data.status);
      setMessage("Comodín equipado.", false);
    });
  });

  trigger.addEventListener("click", () => {
    clickCount += 1;
    if (clickCount >= 5) {
      clickCount = 0;
      modal.show();
      resultEl.innerHTML = "";
      loadStatus().then(loadHistory).then(loadRanking);
    }
  });

  startBtn.addEventListener("click", () => {
    api("/game/start-hand", {method: "POST", body: "{}"}).then(data => {
      if (!data.ok) {
        renderStatus(data.status);
        return setMessage(data.error, true);
      }
      renderStatus(data.status);
      renderCards(data.hand || data.cards, true);
      renderResult(null);
      renderRound(0, false);
      discardBtn.disabled = false;
      keepBtn.disabled = false;
      scoreBtn.disabled = true;
      setMessage("Vuelta 1/3: descartá seleccionadas o mantené cartas.", false);
    });
  });

  function submitDiscard(cards) {
    api("/game/discard", {method: "POST", body: JSON.stringify({cards})}).then(data => {
      if (!data.ok) return setMessage(data.error, true);
      renderCards(data.hand || data.cards, !data.can_score);
      renderRound(data.round, data.can_score);
      discardBtn.disabled = data.can_score;
      keepBtn.disabled = data.can_score;
      scoreBtn.disabled = !data.can_score;
      setMessage(data.can_score ? "Tres vueltas completas. Cerrá la mano para puntuar." : `${data.message}. Seguimos.`, false);
    });
  }

  discardBtn.addEventListener("click", () => submitDiscard(selectedIds()));
  keepBtn.addEventListener("click", () => submitDiscard([]));

  scoreBtn.addEventListener("click", () => {
    api("/game/score", {method: "POST", body: "{}"}).then(data => {
      if (!data.ok) {
        renderStatus(data.status);
        return setMessage(data.error, true);
      }
      renderStatus(data.status);
      renderCards(data.result.final_cards, false);
      discardBtn.disabled = true;
      keepBtn.disabled = true;
      scoreBtn.disabled = true;
      renderResult(data.result, data.unlocked_achievements, data.unlocked_jokers);
      setMessage(`${data.result.result_name}: +${data.result.final_score} puntos ficticios.`, false);
      loadHistory();
      loadRanking();
    });
  });
})();
