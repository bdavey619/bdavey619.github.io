// Yankees Morning Brief — frontend renderer
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
  renderSignals(b.signals);
  renderHot(b.hot_players);
  renderSnapshot(b.team);
  renderAhead(b.next_game, b.standings);
  renderInsight(b.narrative || b.insight, !!b.narrative);
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

  // Story hook — one-sentence emotional frame below the subhead
  if (b.story_hook) {
    const hookEl = document.createElement('p');
    hookEl.id = 'masthead-hook';
    hookEl.className = 'masthead-hook';
    hookEl.textContent = b.story_hook;
    const subheadEl = $('masthead-subhead');
    subheadEl.parentNode.insertBefore(hookEl, subheadEl.nextSibling);
  }
}

function buildSubhead(b) {
  const lg = b.last_game;
  const t = b.team;
  if (!lg || lg.status !== 'final') return '';

  const parts = [];
  const streakMatch = t?.streak?.match(/^W(\d+)/);
  if (streakMatch && parseInt(streakMatch[1]) >= 2) {
    parts.push(`Yankees extend win streak to ${streakMatch[1]}`);
  } else if (lg.result === 'W') {
    parts.push('Yankees win');
  } else {
    parts.push('Yankees fall');
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
    body.innerHTML = `<p class="off-day">No game yesterday — Yankees were off.</p>`;
    show('last-game');
    return;
  }

  const vs = lg.home ? 'vs' : '@';
  const resultClass = lg.result === 'W' ? 'win' : 'loss';
  const gameContext = lg.context_line || (() => {
    const venue = lg.home ? 'Yankee Stadium' : null;
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

  if (lg.highlights_url) {
    html += `<a class="highlights-link" href="${lg.highlights_url}" target="_blank" rel="noopener noreferrer">Watch highlights &#8594;</a>`;
  }

  // Game Driver — overall performance that shaped the game (shown before Turning Point)
  if (lg.game_driver && (lg.game_driver.confidence === 'high' || lg.game_driver.confidence === 'medium')) {
    const gd = lg.game_driver;
    const clutchName = lg.clutch_player?.name;
    if (!clutchName || gd.name !== clutchName) {
      html += `
    <div class="game-driver">
      <span class="game-driver-label">Game Driver</span>
      <p class="game-driver-text"><strong class="game-driver-name">${gd.name}</strong> ${gd.description}</p>
    </div>`;
    }
  }

  if (lg.clutch_player && lg.clutch_player.confidence === 'high') {
    const cp = lg.clutch_player;
    html += `
    <div class="clutch-moment">
      <span class="clutch-label">Turning Point</span>
      <p class="clutch-text"><strong class="clutch-player-name">${cp.name}</strong> ${cp.description}</p>
    </div>`;
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
  const [teamRow, oppRow] = lg.linescore;
  const innings = Math.max(teamRow.length, oppRow.length);

  let head = '<th></th>';
  for (let i = 1; i <= innings; i++) head += `<th>${i}</th>`;
  head += '<th class="total">R</th>';

  const buildRow = (name, row, isTeam) => {
    let cells = `<td class="team">${name}</td>`;
    for (let i = 0; i < innings; i++) {
      const v = row[i];
      cells += `<td>${v === '' || v == null ? '' : v}</td>`;
    }
    cells += `<td class="total">${isTeam ? lg.score.team : lg.score.opp}</td>`;
    return `<tr>${cells}</tr>`;
  };

  // Baseball convention: away team on top, home team on bottom
  const topRow    = lg.home ? buildRow(lg.opponent, oppRow, false) : buildRow('NYY', teamRow, true);
  const bottomRow = lg.home ? buildRow('NYY', teamRow, true)       : buildRow(lg.opponent, oppRow, false);
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

// ---------- signals ----------
function renderSignals(signals) {
  if (!signals || !signals.length) return;
  const list = $('signals-list');
  list.innerHTML = signals.map(s => {
    const text = s && typeof s === 'object' ? `${s.label}: ${s.value}` : String(s);
    return `<li>${text}</li>`;
  }).join('');
  show('signals');
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
      const team = ng.probable.team || 'TBD';
      const opp = ng.probable.opp || 'TBD';
      html += `<div class="probables">${team} vs. ${opp}</div>`;
    }
    if (ng.insight) {
      html += `<div class="next-insight">${ng.insight}</div>`;
    }
    html += `</div>`;
  }

  if (standings?.length) {
    html += `<table class="standings-table">
      <thead><tr><th class="team">AL East</th><th>W</th><th>L</th><th>GB</th><th>L10</th></tr></thead>
      <tbody>`;
    for (const row of standings) {
      const isYankees = /yankees|^nyy$/i.test(row.team);
      html += `<tr class="${isYankees ? 'yankees' : ''}">
        <td class="team">${row.team}</td>
        <td>${row.w}</td>
        <td>${row.l}</td>
        <td>${row.gb}</td>
        <td>${row.last10 || '—'}</td>
      </tr>`;
    }
    html += `</tbody></table>`;

    // Division context: compare Yankees vs leader last-10
    const yankeesRow = standings.find(r => /yankees|^nyy$/i.test(r.team));
    const leaderRow = standings[0];
    if (yankeesRow?.last10 && leaderRow?.last10 && leaderRow !== yankeesRow) {
      html += `<p class="division-context">Yankees ${yankeesRow.last10} in last 10, ${leaderRow.team} ${leaderRow.last10}.</p>`;
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

// ---------- insight / narrative ----------
function renderInsight(ins, isNarrative) {
  if (!ins) return;

  if (isNarrative) {
    // AI-written narrative: top_frame → headline, what_this_means → detail
    if (!ins.top_frame) return;
    $('insight-headline').textContent = ins.top_frame;
    $('insight-detail').textContent   = ins.what_this_means || '';

    // "What to Watch" block — inject before the hidden why element
    if (ins.what_to_watch) {
      let watchEl = document.getElementById('insight-watch');
      if (!watchEl) {
        watchEl = document.createElement('p');
        watchEl.id        = 'insight-watch';
        watchEl.className = 'insight-watch';
        $('insight-why').parentNode.insertBefore(watchEl, $('insight-why'));
      }
      watchEl.textContent = ins.what_to_watch;
      watchEl.hidden = false;
    }
  } else {
    // Legacy deterministic insight
    if (!ins.headline) return;
    $('insight-headline').textContent = ins.headline;
    $('insight-detail').textContent   = ins.detail || '';
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
