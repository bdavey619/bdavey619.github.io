// Padres Morning Brief — frontend renderer
// Reads brief.json and populates the page. Sections hide gracefully if empty.

(async function () {
  try {
    const res = await fetch('./brief.json', { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const brief = await res.json();
    render(brief);
  } catch (err) {
    console.error(err);
    document.getElementById('brief').hidden = true;
    document.getElementById('error').hidden = false;
  }
})();

// ---------- helpers ----------
const $ = (id) => document.getElementById(id);
const show = (id) => { const el = $(id); if (el) el.hidden = false; };
const fmtDate = (iso) => {
  if (!iso) return '';
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
  });
};
const sumRow = (row) =>
  row.reduce((a, v) => a + (typeof v === 'number' ? v : 0), 0);

// ---------- main render ----------
function render(b) {
  renderMasthead(b);
  renderSummaryBar(b);
  renderLastGame(b.last_game);
  renderHot(b.hot_players);
  renderSnapshot(b.team);
  renderAhead(b.next_game, b.standings);
  renderInsight(b.insight);
  renderFooter(b.generated_at);
}

// ---------- masthead ----------
function renderMasthead(b) {
  // Publication date = today, not the last game date
  $('brief-date').textContent = new Date().toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
  });

  // Prefer server-generated subhead (has full data context); fall back to client-side
  const subhead = b.subhead || buildSubhead(b);
  if (subhead) {
    $('masthead-subhead').textContent = subhead;
    $('masthead-subhead').hidden = false;
  }
}

function buildSubhead(b) {
  const lg = b.last_game;
  const t = b.team;
  if (!lg || lg.status !== 'final') return '';

  const parts = [];
  const streakMatch = t?.streak?.match(/^W(\d+)/);
  if (streakMatch && parseInt(streakMatch[1]) >= 2) {
    parts.push(`Padres extend win streak to ${streakMatch[1]}`);
  } else if (lg.result === 'W') {
    parts.push('Padres win');
  } else {
    parts.push('Padres fall');
  }

  const pitcher = lg.key_pitcher?.name;
  const hitter = lg.key_hitters?.[0]?.name;
  if (pitcher && hitter) {
    parts.push(`behind ${pitcher} and ${hitter}`);
  } else if (pitcher) {
    parts.push(`behind ${pitcher}`);
  } else if (hitter) {
    parts.push(`behind ${hitter}`);
  }

  return parts.join(' ') + '.';
}

// ---------- summary bar ----------
function renderSummaryBar(b) {
  const t = b.team || {};
  const lg = b.last_game || {};
  const ng = b.next_game;
  if (!t.record && !lg.result && !ng) return;

  $('sb-record').textContent = t.record || '—';
  $('sb-rank').textContent = t.division_rank ? `#${t.division_rank}` : '—';
  $('sb-streak').textContent = t.streak || '—';
  $('sb-last10').textContent = t.last10 || '—';

  if (lg.status === 'final' && lg.score) {
    const vs = lg.home ? 'vs' : '@';
    $('sb-last').textContent = `${lg.result} ${lg.score.team}-${lg.score.opp}`;
  } else {
    $('sb-last').textContent = '—';
  }

  if (ng) {
    const vs = ng.home ? 'vs' : '@';
    $('sb-next').textContent = `${vs} ${ng.opponent}`;
  } else {
    $('sb-next').textContent = '—';
  }

  show('summary-bar');
}

// ---------- last game ----------
function renderLastGame(lg) {
  if (!lg) return;
  const body = $('last-game-body');

  if (lg.status !== 'final') {
    body.innerHTML = `<p class="off-day">No game yesterday — Padres were off.</p>`;
    show('last-game');
    return;
  }

  const vs = lg.home ? 'vs' : '@';
  const resultClass = lg.result === 'W' ? 'win' : 'loss';
  const gameContext = lg.context_line || (() => {
    const venue = lg.home ? 'Petco Park' : null;
    const parts = [lg.home ? 'Home' : 'Away'];
    if (venue) parts.push(venue);
    return parts.join(' · ');
  })();
  // Prepend the actual game date so it's unambiguous (brief date ≠ game date on off days)
  const gameDateLabel = lg.date ? new Date(...lg.date.split('-').map((v, i) => i === 1 ? v - 1 : +v))
    .toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }) : '';
  const contextLine = [gameDateLabel, gameContext].filter(Boolean).join(' · ');

  let html = `
    <div class="lg-headline">
      <span class="lg-score">${lg.score.team}–${lg.score.opp}</span>
      <span class="lg-result ${resultClass}">${lg.result}</span>
      <span class="lg-vs">${vs} ${lg.opponent}</span>
    </div>
    <div class="lg-context">${contextLine}</div>
  `;

  if (lg.game_note) {
    html += `<p class="lg-game-note">${lg.game_note}</p>`;
  }

  html += renderLinescore(lg);
  html += renderDecisions(lg.decisions);

  if (lg.key_hitters?.length) {
    html += `<div class="performer-label">Key hitters</div><div class="performers">`;
    for (const h of lg.key_hitters) {
      const meta = [h.pos, h.season_avg].filter(Boolean).join(' · ');
      const label = meta ? `${h.name} (${meta})` : h.name;
      html += `<div class="performer"><span class="name">${label}</span><span class="line">${h.line}</span></div>`;
    }
    html += `</div>`;
  }

  if (lg.key_pitcher) {
    const kp = lg.key_pitcher;
    const meta = [kp.role, kp.season_era].filter(Boolean).join(' · ');
    const label = meta ? `${kp.name} (${meta})` : kp.name;
    html += `<div class="performer-label">Key pitcher</div><div class="performers">
      <div class="performer"><span class="name">${label}</span><span class="line">${kp.line}</span></div>
    </div>`;
  }

  html += renderFullBoxScore(lg.full_box);

  body.innerHTML = html;
  show('last-game');
}

function renderLinescore(lg) {
  if (!lg.linescore || !lg.linescore[0]?.length) return '';
  const [sdRow, oppRow] = lg.linescore;
  const innings = Math.max(sdRow.length, oppRow.length);

  let head = '<th></th>';
  for (let i = 1; i <= innings; i++) head += `<th>${i}</th>`;
  head += '<th class="total">R</th>';

  const buildRow = (name, row, isPadres) => {
    let cells = `<td class="team">${name}</td>`;
    for (let i = 0; i < innings; i++) {
      const v = row[i];
      cells += `<td>${v === '' || v == null ? '' : v}</td>`;
    }
    cells += `<td class="total">${isPadres ? lg.score.team : lg.score.opp}</td>`;
    return `<tr>${cells}</tr>`;
  };

  // Baseball convention: away team on top, home team on bottom
  const topRow    = lg.home ? buildRow(lg.opponent, oppRow, false) : buildRow('SD', sdRow, true);
  const bottomRow = lg.home ? buildRow('SD', sdRow, true)         : buildRow(lg.opponent, oppRow, false);
  return `
    <div class="linescore">
      <table>
        <thead><tr>${head}</tr></thead>
        <tbody>
          ${topRow}
          ${bottomRow}
        </tbody>
      </table>
    </div>
  `;
}

function renderDecisions(d) {
  if (!d || (!d.win && !d.loss && !d.save)) return '';
  const parts = [];
  const fmtDecision = (name, role) => role ? `${name} (${role})` : name;
  if (d.win) parts.push(`<span><strong>W:</strong> ${fmtDecision(d.win, d.win_role)}</span>`);
  if (d.loss) parts.push(`<span><strong>L:</strong> ${fmtDecision(d.loss, d.loss_role)}</span>`);
  if (d.save) parts.push(`<span><strong>SV:</strong> ${d.save}</span>`);
  return `<div class="decisions">${parts.join('')}</div>`;
}

// ---------- hot players ----------
function renderHot(hot) {
  if (!hot) return;
  const hitters = hot.hitters || [];
  const pitchers = hot.pitchers || [];
  if (!hitters.length && !pitchers.length) return; // hide entirely in V1

  let html = '';
  if (hitters.length) {
    html += `<div class="performer-label">Hitters</div><div class="performers">`;
    for (const h of hitters) {
      html += `<div class="performer"><span class="name">${h.name}</span><span class="line">${h.stat || h.line || ''}</span></div>`;
    }
    html += `</div>`;
  }
  if (pitchers.length) {
    html += `<div class="performer-label">Pitchers</div><div class="performers">`;
    for (const p of pitchers) {
      html += `<div class="performer"><span class="name">${p.name}</span><span class="line">${p.stat || p.line || ''}</span></div>`;
    }
    html += `</div>`;
  }
  $('hot-body').innerHTML = html;
  show('hot');
}

// ---------- snapshot ----------
function renderSnapshot(t) {
  if (!t) return;
  const fields = [
    ['Record', t.record],
    ['Run Diff', t.run_diff],
    ['Last 10', t.last10],
    ['AVG', t.avg],
    ['OPS', t.ops],
    ['ERA', t.era],
  ].filter(([, v]) => v && v !== '-');
  if (!fields.length) return;

  $('snapshot-body').innerHTML = fields
    .map(([label, value]) => `<div><span class="label">${label}</span><span class="value">${value}</span></div>`)
    .join('');
  show('snapshot');
}

// ---------- looking ahead ----------
function renderAhead(ng, standings) {
  let html = '';

  if (ng) {
    const vs = ng.home ? 'vs' : '@';
    html += `<div class="next-game">
      <div class="matchup">${vs} ${ng.opponent}</div>
      <div class="meta">${fmtDate(ng.date)} · ${ng.time_local || ''}</div>`;
    if (ng.probable && (ng.probable.team || ng.probable.opp)) {
      const sd = ng.probable.team || 'TBD';
      const opp = ng.probable.opp || 'TBD';
      html += `<div class="probables">${sd} vs. ${opp}</div>`;
    }
    if (ng.insight) {
      html += `<div class="next-insight">${ng.insight}</div>`;
    }
    html += `</div>`;
  }

  if (standings?.length) {
    html += `<table class="standings-table">
      <thead><tr><th class="team">NL West</th><th>W</th><th>L</th><th>GB</th><th>L10</th></tr></thead>
      <tbody>`;
    for (const row of standings) {
      const isPadres = /padres|^sd$/i.test(row.team);
      html += `<tr class="${isPadres ? 'padres' : ''}">
        <td class="team">${row.team}</td>
        <td>${row.w}</td>
        <td>${row.l}</td>
        <td>${row.gb}</td>
        <td>${row.last10 || '—'}</td>
      </tr>`;
    }
    html += `</tbody></table>`;

    // Division context: compare Padres vs leader last-10
    const padresRow = standings.find(r => /padres|^sd$/i.test(r.team));
    const leaderRow = standings[0];
    if (padresRow?.last10 && leaderRow?.last10 && leaderRow !== padresRow) {
      html += `<p class="division-context">Padres ${padresRow.last10} in last 10, ${leaderRow.team} ${leaderRow.last10}.</p>`;
    }
  }

  if (!html) return;
  $('ahead-body').innerHTML = html;
  show('ahead');
}

function renderFullBoxScore(box) {
  if (!box) return '';
  let inner = '';

  if (box.batting?.length) {
    // Find the top batter: most hits, tiebreak by HR then RBI
    let topIdx = 0;
    let topScore = -1;
    box.batting.forEach((r, i) => {
      const s = r.h * 100 + (r.rbi || 0) * 10 + (r.r || 0);
      if (s > topScore) { topScore = s; topIdx = i; }
    });

    inner += `<div class="box-score-label">Batting</div>
      <table class="box-score-table">
        <thead><tr>
          <th class="player">Player</th>
          <th>AB</th><th>R</th><th>H</th><th>RBI</th><th>BB</th><th>SO</th>
        </tr></thead>
        <tbody>`;
    box.batting.forEach((r, i) => {
      const cls = (i === topIdx && topScore > 0) ? ' class="standout"' : '';
      const meta = [r.pos, r.avg].filter(Boolean).join(' · ');
      const metaHtml = meta ? ` <span class="player-meta">${meta}</span>` : '';
      inner += `<tr${cls}>
        <td class="player">${r.name}${metaHtml}</td>
        <td>${r.ab}</td><td>${r.r}</td><td>${r.h}</td>
        <td>${r.rbi}</td><td>${r.bb}</td><td>${r.so}</td>
      </tr>`;
    });
    inner += `</tbody></table>`;
  }

  if (box.pitching?.length) {
    inner += `<div class="box-score-label">Pitching</div>
      <table class="box-score-table">
        <thead><tr>
          <th class="player">Pitcher</th>
          <th>IP</th><th>H</th><th>ER</th><th>K</th><th>BB</th>
        </tr></thead>
        <tbody>`;
    box.pitching.forEach((r, i) => {
      // First pitcher in the list is always the starter
      const cls = i === 0 ? ' class="standout"' : '';
      inner += `<tr${cls}>
        <td class="player">${r.name}</td>
        <td>${r.ip}</td><td>${r.h}</td><td>${r.er}</td>
        <td>${r.k}</td><td>${r.bb}</td>
      </tr>`;
    });
    inner += `</tbody></table>`;
  }

  if (!inner) return '';
  return `
    <details class="box-score-details">
      <summary>Full Box Score</summary>
      <div class="box-score-inner">${inner}</div>
    </details>`;
}

// ---------- insight ----------
function renderInsight(ins) {
  if (!ins || !ins.headline) return;
  $('insight-headline').textContent = ins.headline;
  $('insight-detail').textContent = ins.detail || '';
  if (ins.why) {
    const el = $('insight-why');
    el.textContent = ins.why;
    el.hidden = false;
  }
  show('insight');
}

// ---------- footer ----------
function renderFooter(ts) {
  if (!ts) return;
  try {
    const d = new Date(ts);
    $('generated-at').textContent = `Generated ${d.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })}`;
  } catch {
    $('generated-at').textContent = ts;
  }
}
