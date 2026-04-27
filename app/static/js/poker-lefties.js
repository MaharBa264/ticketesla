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
  const historyEl = document.getElementById("pokerHistory");
  const jokersEl = document.getElementById("pokerJokers");
  const achievementsEl = document.getElementById("pokerAchievements");
  const rankingEl = document.getElementById("pokerRanking");
  const startBtn = document.getElementById("pokerStart");
  const discardBtn = document.getElementById("pokerDiscard");
  const scoreBtn = document.getElementById("pokerScore");
  let clickCount = 0;
  let activeCards = [];

  function api(path, options) {
    const opts = options || {};
    opts.headers = Object.assign({"X-CSRFToken": csrf, "Content-Type": "application/json"}, opts.headers || {});
    return fetch(path, opts).then(r => r.json());
  }

  function setMessage(text, error) {
    msgEl.textContent = text || "";
    msgEl.classList.toggle("is-error", Boolean(error));
  }

  function renderStatus(status) {
    if (!status) return;
    pointsEl.textContent = status.points_total;
    handsEl.textContent = status.hands_remaining + "/" + status.hands_limit;
    streakEl.textContent = status.streak_current + "/" + status.streak_best;
    resetEl.textContent = status.resets_at || "-";
    startBtn.disabled = !status.enabled || status.hands_remaining <= 0;
    renderJokers(status.jokers);
    renderAchievements(status.achievements);
  }

  function suitClass(card) {
    return card.suit === "H" || card.suit === "D" ? "is-red" : "is-black";
  }

  function renderCards(cards, selectable) {
    activeCards = cards || [];
    cardsEl.innerHTML = "";
    if (!activeCards.length) {
      cardsEl.innerHTML = '<div class="poker16-empty">Esperando mano...</div>';
      return;
    }
    activeCards.forEach(card => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "poker16-card " + suitClass(card);
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

  function bonusText(item) {
    if (item.kind === "multiplier") return `${item.name} x${(1 + item.amount).toFixed(2)}`;
    return `${item.name} +${item.amount}`;
  }

  function renderResult(result, unlocked) {
    if (!result) {
      resultEl.innerHTML = "";
      return;
    }
    const bonuses = (result.bonuses || []).map(b => `<span>${bonusText(b)}</span>`).join("");
    const achievements = (unlocked || []).map(a => `<span>LOGRO: ${a.name} +${a.points_reward}</span>`).join("");
    resultEl.innerHTML = `
      <div class="poker16-score-card">
        <strong>${result.name}</strong>
        <em>${result.base_score} base + bonos x${result.multiplier} = ${result.score}</em>
        <div class="poker16-bonus-list">${bonuses || "<span>Sin bonos. Manual de operador, pagina 404.</span>"}${achievements}</div>
      </div>`;
  }

  function renderHistory(hands) {
    historyEl.innerHTML = "";
    if (!hands || hands.length === 0) {
      historyEl.innerHTML = '<div class="poker16-empty">Todavia no hay manos jugadas.</div>';
      return;
    }
    hands.forEach(hand => {
      const row = document.createElement("div");
      row.className = "poker16-history-row";
      row.innerHTML = `<span>${hand.played_at}</span><strong>${hand.result_name}</strong><em>+${hand.score}</em>`;
      historyEl.appendChild(row);
    });
  }

  function renderJokers(jokers) {
    jokersEl.innerHTML = "";
    const items = jokers && jokers.items ? jokers.items : [];
    if (!items.length) {
      jokersEl.innerHTML = '<div class="poker16-empty">Jugando se desbloquean comodines.</div>';
      return;
    }
    items.forEach(joker => {
      const card = document.createElement("div");
      card.className = "poker16-joker" + (joker.equipped_slot ? " equipped" : "");
      card.innerHTML = `
        <strong>${joker.name}</strong>
        <p>${joker.description}</p>
        <small>${joker.equipped_slot ? "Equipado slot " + joker.equipped_slot : joker.unlock_rule}</small>
        <div>
          <button type="button" data-joker-code="${joker.code}" data-joker-slot="1">S1</button>
          <button type="button" data-joker-code="${joker.code}" data-joker-slot="2">S2</button>
        </div>`;
      jokersEl.appendChild(card);
    });
  }

  function renderAchievements(items) {
    achievementsEl.innerHTML = "";
    if (!items || !items.length) {
      achievementsEl.innerHTML = '<div class="poker16-empty">Sin logros todavia. El sistema esta mirando.</div>';
      return;
    }
    items.forEach(item => {
      const row = document.createElement("div");
      row.className = "poker16-achievement";
      row.innerHTML = `<strong>${item.name}</strong><span>${item.description}</span><small>${item.unlocked_at} / +${item.points_reward}</small>`;
      achievementsEl.appendChild(row);
    });
  }

  function renderRanking(data) {
    if (!data || !data.enabled) {
      rankingEl.innerHTML = '<div class="poker16-empty">Ranking deshabilitado para este usuario.</div>';
      return;
    }
    const sections = [
      ["Puntos totales", data.ranking.points],
      ["Mejor mano", data.ranking.best_hand],
      ["Racha", data.ranking.streak]
    ];
    rankingEl.innerHTML = sections.map(([title, rows]) => `
      <div class="poker16-rank-panel">
        <strong>${title}</strong>
        ${(rows || []).map((row, index) => `<div><span>${index + 1}. ${row.name} / ${row.area}</span><em>${row.value}</em></div>`).join("") || '<small>Sin datos.</small>'}
      </div>`).join("");
  }

  function loadHistory() {
    return api("/game/history", {method: "GET"}).then(data => renderHistory(data.hands));
  }

  function loadRanking() {
    return api("/game/ranking", {method: "GET"}).then(renderRanking);
  }

  function loadStatus() {
    return api("/game/status", {method: "GET"}).then(data => {
      renderStatus(data.status);
      if (data.active_hand) {
        renderCards(data.active_hand.final || data.active_hand.dealt, !data.active_hand.discard_used);
        discardBtn.disabled = Boolean(data.active_hand.discard_used);
        scoreBtn.disabled = false;
      } else {
        renderCards([], false);
        discardBtn.disabled = true;
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
    const button = event.target.closest("[data-joker-code]");
    if (!button) return;
    api("/game/equip-joker", {method: "POST", body: JSON.stringify({code: button.dataset.jokerCode, slot: button.dataset.jokerSlot})}).then(data => {
      if (!data.ok) {
        setMessage(data.error, true);
        return;
      }
      renderStatus(data.status);
      setMessage("Comodin actualizado.", false);
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
        setMessage(data.error, true);
        renderStatus(data.status);
        return;
      }
      renderStatus(data.status);
      renderCards(data.cards, true);
      renderResult(null);
      discardBtn.disabled = false;
      scoreBtn.disabled = false;
      setMessage("Selecciona cartas y descarta una vez, o puntua directo.", false);
    });
  });

  discardBtn.addEventListener("click", () => {
    api("/game/discard", {method: "POST", body: JSON.stringify({discarded_ids: selectedIds()})}).then(data => {
      if (!data.ok) {
        setMessage(data.error, true);
        return;
      }
      renderCards(data.cards, false);
      discardBtn.disabled = true;
      scoreBtn.disabled = false;
      setMessage("Descarte ejecutado. Puntua cuando quieras.", false);
    });
  });

  scoreBtn.addEventListener("click", () => {
    api("/game/score", {method: "POST", body: "{}"}).then(data => {
      if (!data.ok) {
        setMessage(data.error, true);
        renderStatus(data.status);
        return;
      }
      renderStatus(data.status);
      renderCards(data.result.final_cards, false);
      discardBtn.disabled = true;
      scoreBtn.disabled = true;
      renderResult(data.result, data.unlocked_achievements);
      setMessage(`${data.result.name}: +${data.result.score} puntos ficticios.`, false);
      loadHistory();
      loadRanking();
    });
  });
})();
