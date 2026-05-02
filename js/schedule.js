(function () {
  'use strict';

  const cfg = window.SCHEDULE_CONFIG;
  let _index = null; // { season, months: ["2026-03", ...] }

  async function init() {
    // Load month index — nav degrades gracefully if missing
    try {
      const r = await fetch('./schedule-index.json');
      if (r.ok) _index = await r.json();
    } catch (_) {}

    const active = resolveActiveMonth();
    await loadAndRender(active);

    window.addEventListener('popstate', () => {
      loadAndRender(resolveActiveMonth());
    });
  }

  function availableMonths() {
    return (_index && _index.months && _index.months.length) ? _index.months : null;
  }

  function resolveActiveMonth() {
    const param = new URLSearchParams(window.location.search).get('month');
    const months = availableMonths();
    const today = todayStr().slice(0, 7); // YYYY-MM

    if (param) {
      // Accept param if index is absent (file may still exist) or param is in index
      if (!months || months.includes(param)) return param;
    }
    if (!months) return today;
    if (months.includes(today)) return today;
    // Outside season — clamp to first or last available month
    if (today < months[0]) return months[0];
    return months[months.length - 1];
  }

  async function loadAndRender(monthKey) {
    try {
      const r = await fetch(`./schedule-${monthKey}.json`);
      if (!r.ok) throw new Error(r.status);
      const data = await r.json();
      renderAll(data, monthKey);
    } catch (_) {
      // Fall back to legacy schedule.json if per-month file is missing
      try {
        const r2 = await fetch('./schedule.json');
        if (!r2.ok) throw new Error(r2.status);
        const data = await r2.json();
        renderAll(data, data.month || monthKey);
      } catch (_2) {
        document.getElementById('cal-error').removeAttribute('hidden');
      }
    }
  }

  function renderAll(data, monthKey) {
    renderSummary(data);
    renderNav(monthKey);
    renderCalendar(data);
    document.getElementById('schedule-cal').removeAttribute('hidden');
  }

  // ── Summary bar ──────────────────────────────────────────────────────────

  function renderSummary(data) {
    const today = todayStr();
    const next = data.games.find(g => g.date >= today && g.status === 'scheduled');

    set('sc-month-record', data.summary.month_record || '—');
    set('sc-streak', data.summary.current_streak || '—');
    set('sc-last10', data.summary.last_10 || '—');
    set('sc-next', next ? (next.home ? 'vs ' : '@ ') + next.opponent : '—');
    document.getElementById('schedule-summary').removeAttribute('hidden');
  }

  // ── Month navigation ──────────────────────────────────────────────────────

  function renderNav(monthKey) {
    const months = availableMonths();
    const idx = months ? months.indexOf(monthKey) : -1;

    const prevBtn = document.getElementById('cal-prev-month');
    const nextBtn = document.getElementById('cal-next-month');

    if (prevBtn) {
      const hasPrev = idx > 0;
      prevBtn.disabled = !hasPrev;
      prevBtn.onclick = hasPrev ? () => navigate(months[idx - 1]) : null;
    }
    if (nextBtn) {
      const hasNext = months && idx >= 0 && idx < months.length - 1;
      nextBtn.disabled = !hasNext;
      nextBtn.onclick = hasNext ? () => navigate(months[idx + 1]) : null;
    }
  }

  function navigate(monthKey) {
    const url = new URL(window.location.href);
    url.searchParams.set('month', monthKey);
    history.pushState({ month: monthKey }, '', url.toString());
    loadAndRender(monthKey);
  }

  // ── Calendar grid ─────────────────────────────────────────────────────────

  function daysBetween(d1, d2) {
    return (new Date(d2) - new Date(d1)) / 86400000;
  }

  // Group games into series: same opponent + home/away, gap ≤ 2 calendar days
  // (allows one off-day between consecutive games in the same series).
  // Returns Map<gamePk, {len, pos, seriesResult}> where seriesResult is
  // "won" | "lost" | "split" for fully completed multi-game series, else null.
  function buildSeriesMeta(games) {
    // Build series groups
    const seriesList = [];
    let curr = null;

    for (const g of games) {
      if (
        curr &&
        g.opponent === curr.opp &&
        g.home === curr.home &&
        daysBetween(curr.lastDate, g.date) <= 2
      ) {
        curr.games.push(g);
        curr.lastDate = g.date;
      } else {
        if (curr) seriesList.push(curr);
        curr = { opp: g.opponent, home: g.home, lastDate: g.date, games: [g] };
      }
    }
    if (curr) seriesList.push(curr);

    // Compute result for each series and build lookup map
    const meta = new Map();

    for (const s of seriesList) {
      const len = s.games.length;

      // Only shade multi-game series where every game is final
      const allFinal = len > 1 && s.games.every(g => g.status === 'final');
      let seriesResult = null;
      if (allFinal) {
        const wins   = s.games.filter(g => g.result === 'W').length;
        const losses = s.games.filter(g => g.result === 'L').length;
        seriesResult = wins > losses ? 'won' : losses > wins ? 'lost' : 'split';
        console.log('Series:', s.opp, seriesResult, s.games.map(g => g.date));
      }

      s.games.forEach((g, i) => {
        meta.set(g.gamePk, { len, pos: i + 1, seriesResult });
      });
    }

    return meta;
  }

  function renderCalendar(data) {
    const [year, month] = data.month.split('-').map(Number);
    const monthLabel = new Date(year, month - 1, 1)
      .toLocaleString('en-US', { month: 'long', year: 'numeric' });

    set('cal-month-title', monthLabel);

    const byDate = {};
    for (const g of data.games) {
      if (!byDate[g.date]) byDate[g.date] = [];
      byDate[g.date].push(g);
    }

    const seriesMeta = buildSeriesMeta(data.games);

    const grid = document.getElementById('calendar-grid');
    grid.innerHTML = ''; // clear on re-render

    const firstDow = new Date(year, month - 1, 1).getDay();
    const daysInMonth = new Date(year, month, 0).getDate();
    const today = todayStr();
    const totalCells = Math.ceil((firstDow + daysInMonth) / 7) * 7;

    // Day-of-week header row
    const header = el('div', 'cal-header-row');
    for (const d of ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']) {
      const h = el('div', 'cal-header-cell');
      h.textContent = d;
      header.appendChild(h);
    }
    grid.appendChild(header);

    let row = null;
    for (let i = 0; i < totalCells; i++) {
      if (i % 7 === 0) {
        row = el('div', 'cal-row');
        grid.appendChild(row);
      }

      const dayNum = i - firstDow + 1;
      const cell = el('div', 'cal-cell');

      if (dayNum < 1 || dayNum > daysInMonth) {
        cell.classList.add('cal-empty');
      } else {
        const dateStr = isoDate(year, month, dayNum);
        if (dateStr === today) cell.classList.add('cal-today');

        const dateGames = byDate[dateStr] || [];
        // Mark cells that belong to a multi-game series for subtle grouping
        if (dateGames.some(g => { const s = seriesMeta.get(g.gamePk); return s && s.len > 1; })) {
          cell.classList.add('cal-series-cell');
        }
        // Apply completed-series result tint to the cell (behind game cards)
        const cellSeriesResult = (() => {
          for (const g of dateGames) {
            const s = seriesMeta.get(g.gamePk);
            if (s && s.seriesResult) return s.seriesResult;
          }
          return null;
        })();
        if (cellSeriesResult) {
          cell.dataset.seriesResult = cellSeriesResult;
          cell.title = `Series ${cellSeriesResult}`;
        }

        const num = el('span', 'cal-day-num');
        num.textContent = dayNum;
        cell.appendChild(num);

        for (const g of dateGames) {
          cell.appendChild(buildGame(g, seriesMeta.get(g.gamePk)));
        }
      }

      row.appendChild(cell);
    }
  }

  function buildGame(g, series) {
    const wrap = el('div', 'cal-game');
    wrap.classList.add(g.home ? 'cal-home' : 'cal-away');

    // Opening Day label (before opponent line so it reads top-to-bottom)
    if (g.opening_day) {
      const od = el('div', 'cal-opening-day');
      od.textContent = 'Opening Day';
      wrap.appendChild(od);
    }

    // Opponent line — split prefix from team abbr for independent styling
    const oppRow = el('div', 'cal-opp');
    const haSpan = el('span', 'cal-ha');
    haSpan.textContent = g.home ? 'VS' : '@';
    const nameSpan = el('span', 'cal-opp-name');
    nameSpan.textContent = g.opponent;
    oppRow.appendChild(haSpan);
    oppRow.appendChild(nameSpan);
    wrap.appendChild(oppRow);

    if (g.status === 'final') {
      wrap.classList.add('cal-game-final');
      wrap.classList.add(g.result === 'W' ? 'cal-win' : 'cal-loss');

      const res = el('div', 'cal-result');
      const badge = el('span', 'cal-badge');
      badge.textContent = g.result;
      const score = el('span', 'cal-score');
      score.textContent = g.score;
      res.appendChild(badge);
      res.appendChild(score);
      wrap.appendChild(res);

      if (g.archive_url) {
        wrap.classList.add('cal-linked');
        wrap.setAttribute('role', 'link');
        wrap.setAttribute('tabindex', '0');
        wrap.title = `View brief for ${g.date}`;
        wrap.addEventListener('click', () => { window.location.href = g.archive_url; });
        wrap.addEventListener('keydown', e => {
          if (e.key === 'Enter' || e.key === ' ') window.location.href = g.archive_url;
        });
      }
    } else {
      wrap.classList.add('cal-game-upcoming');

      const time = el('div', 'cal-time');
      time.textContent = g.status === 'live' ? 'Live' : (g.time_local || 'TBD');
      if (g.status === 'live') time.classList.add('cal-live');
      wrap.appendChild(time);

      if (g.probable && (g.probable.team || g.probable.opp)) {
        const prob = el('div', 'cal-probable');
        const parts = [];
        if (g.probable.team) parts.push(lastName(g.probable.team));
        if (g.probable.opp) parts.push(lastName(g.probable.opp));
        prob.textContent = parts.join(' / ');
        wrap.appendChild(prob);
      }
    }

    return wrap;
  }

  function lastName(name) {
    const parts = name.trim().split(/\s+/);
    return parts[parts.length - 1];
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  function el(tag, cls) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    return e;
  }

  function set(id, text) {
    const e = document.getElementById(id);
    if (e) e.textContent = text;
  }

  function todayStr() {
    return new Date().toISOString().slice(0, 10);
  }

  function isoDate(year, month, day) {
    return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  }

  init();
}());
