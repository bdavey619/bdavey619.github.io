(function () {
  'use strict';

  const cfg = window.SCHEDULE_CONFIG;

  async function init() {
    try {
      const r = await fetch('./schedule.json');
      if (!r.ok) throw new Error(r.status);
      const data = await r.json();
      render(data);
    } catch (_) {
      document.getElementById('cal-error').removeAttribute('hidden');
    }
  }

  function render(data) {
    renderSummary(data);
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
    if (next) {
      set('sc-next', (next.home ? 'vs ' : '@ ') + next.opponent);
    } else {
      set('sc-next', '—');
    }
    document.getElementById('schedule-summary').removeAttribute('hidden');
  }

  // ── Calendar grid ─────────────────────────────────────────────────────────

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

    const grid = document.getElementById('calendar-grid');
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

        const num = el('span', 'cal-day-num');
        num.textContent = dayNum;
        cell.appendChild(num);

        for (const g of (byDate[dateStr] || [])) {
          cell.appendChild(buildGame(g));
        }
      }

      row.appendChild(cell);
    }
  }

  function buildGame(g) {
    const wrap = el('div', 'cal-game');
    const ha = g.home ? 'vs' : '@';

    if (g.status === 'final') {
      wrap.classList.add('cal-game-final');
      wrap.classList.add(g.result === 'W' ? 'cal-win' : 'cal-loss');

      const opp = el('span', 'cal-opp');
      opp.textContent = `${ha} ${g.opponent}`;
      wrap.appendChild(opp);

      const res = el('span', 'cal-result');
      res.textContent = `${g.result} ${g.score}`;
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

      const opp = el('span', 'cal-opp');
      opp.textContent = `${ha} ${g.opponent}`;
      wrap.appendChild(opp);

      const time = el('span', 'cal-time');
      time.textContent = g.status === 'live' ? 'Live' : (g.time_local || 'TBD');
      if (g.status === 'live') time.classList.add('cal-live');
      wrap.appendChild(time);

      if (g.probable && (g.probable.team || g.probable.opp)) {
        const prob = el('span', 'cal-probable');
        const parts = [];
        if (g.probable.team) parts.push(g.probable.team);
        if (g.probable.opp) parts.push(g.probable.opp);
        prob.textContent = parts.join(' vs ');
        wrap.appendChild(prob);
      }
    }

    return wrap;
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
