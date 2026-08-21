function h2hScore(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(1) : '-';
}

function h2hSigned(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '-';
  return `${n > 0 ? '+' : ''}${n.toFixed(1)}`;
}

function h2hSignalClass(signal) {
  if (signal === 'EDGE') return 'edge';
  if (signal === 'TRAIL') return 'trail';
  return 'even';
}

function pressureClass(level) {
  return String(level || 'LOW').toLowerCase().replaceAll(' ', '-');
}

function h2hPlayerProjection(playerId, side) {
  const rows = side?.projection?.players || [];
  return rows.find(row => String(row.player_id) === String(playerId)) || {};
}

function h2hPlayerRow(player, side) {
  const selection = player.selection || {};
  const projection = h2hPlayerProjection(player.player_id, side);
  const gw = DATA.h2h_matchup?.gameweek || DATA.planning_gameweeks?.[0] || 1;
  return `<button class="h2h-player-row" data-player-id="${esc(player.player_id)}">
    ${recommendedKit(player, true)}
    <span class="h2h-player-name"><strong>${esc(player.player)}</strong><small>${esc(player.position)} · ${esc(player.club || '-')} · ${esc(fixtureLabel(player, gw))}</small></span>
    <span class="h2h-player-score"><small>Proj.</small><strong>${esc(h2hScore(projection.projected_points))}</strong><em>Start ${esc(h2hScore(selection.start_score))}</em></span>
  </button>`;
}

function h2hThreatCard(player, label) {
  return `<button class="h2h-threat-card" data-player-id="${esc(player.player_id)}">
    <span class="h2h-threat-label">${esc(label)}</span>
    <div class="h2h-threat-head">${recommendedKit(player, true)}<div><strong>${esc(player.player)}</strong><small>${esc(player.position)} · ${esc(player.club || '-')}</small></div></div>
    <div class="h2h-threat-metrics"><span><small>Projected</small><b>${esc(h2hScore(player.projected_points))}</b></span><span><small>Roster</small><b>${esc(h2hScore(player.roster_value))}</b></span></div>
    <small class="h2h-threat-fixture">${esc(player.fixture || '-')} · ${esc(player.role_evidence || 'LOW')} evidence</small>
  </button>`;
}

function h2hPriorityCard(priority) {
  const counter = priority.counter;
  return `<article class="h2h-priority">
    <div><span class="h2h-priority-label">${esc(priority.action)}</span>${priority.position ? `<strong>${esc(priority.position)}</strong>` : ''}</div>
    <p>${esc(priority.reason || '')}</p>
    ${counter ? `<button class="h2h-counter" data-player-id="${esc(counter.add_player_id)}"><span>Add ${esc(counter.add_player)} · Drop ${esc(counter.drop_player)}</span><strong>${esc(h2hSigned(counter.projected_points_delta))} projected pts</strong><small>${esc(counter.replacement_action || 'CONSIDER')} · Roster ${esc(h2hSigned(counter.roster_value_delta))} · ${esc(counter.role_evidence || 'LOW')} evidence</small></button>` : ''}
  </article>`;
}

function scoutWeakStarter(row) {
  if (!row) return 'None identified';
  return `${esc(row.player)} · ${esc(row.position)} · ${esc(h2hScore(row.projected_points))} proj.`;
}

function renderH2H() {
  const h2h = DATA.h2h_matchup;
  if (!h2h || !h2h.available) {
    return `<section class="h2h-v08"><div class="h2h-empty"><div class="eyebrow">H2H Scout · v1.0</div><h3>Opponent comparison unavailable</h3><p>${esc(h2h?.reason || 'The current league payload did not expose enough H2H matchup data yet.')}</p></div></section>`;
  }
  const matchup = h2h.matchup || {};
  const mine = matchup.my || {};
  const opponent = matchup.opponent || {};
  const myProjection = mine.projection || {};
  const opponentProjection = opponent.projection || {};
  const pressure = matchup.pressure || {};
  const scouting = h2h.scouting || {};
  const oppScout = scouting.opponent || {};
  const bestMove = scouting.best_matchup_move || null;
  const opponentMeta = h2h.opponent || {};
  const opponentName = opponentMeta.display_name || 'League opponent';
  const rank = opponentMeta.rank != null ? `Rank #${esc(opponentMeta.rank)}` : 'Preseason rank pending';
  const myLineup = h2h.my_lineup?.starters || [];
  const opponentLineup = h2h.opponent_lineup?.starters || [];
  const positions = matchup.position_edges || [];
  const threats = h2h.opponent_threats || [];
  const counters = h2h.my_counterweights || [];
  const priorities = h2h.tactical_priorities || [];
  return `<section class="h2h-v08 h2h-v10">
    <div class="h2h-intro">
      <div><div class="eyebrow">H2H Scout · v1.0 · GW${esc(h2h.gameweek)}</div><h3>Scout the matchup before you change the squad</h3><p>Projected points estimate the likely XI outcome from blended points-per-90, expected minutes, availability and fixture difficulty. Start Score remains the lineup-selection heuristic.</p></div>
      <div class="h2h-opponent"><small>Upcoming opponent</small><strong>${esc(opponentName)}</strong><span>${rank}${opponentMeta.h2h_points != null ? ` · ${esc(opponentMeta.h2h_points)} H2H pts` : ''}</span></div>
    </div>

    <div class="h2h-projection-balance ${h2hSignalClass(matchup.signal)}">
      <div><small>Your projected XI</small><strong>${esc(h2hScore(myProjection.total))}</strong><span>${esc(h2hScore(myProjection.range_low))}–${esc(h2hScore(myProjection.range_high))} uncertainty band</span></div>
      <div class="h2h-balance-centre"><span class="h2h-signal">${esc(matchup.signal || 'EVEN')}</span><strong>${esc(h2hSigned(matchup.projected_points_edge))}</strong><small>projected-point edge</small></div>
      <div><small>Opponent projected XI</small><strong>${esc(h2hScore(opponentProjection.total))}</strong><span>${esc(h2hScore(opponentProjection.range_low))}–${esc(h2hScore(opponentProjection.range_high))} uncertainty band</span></div>
    </div>

    <div class="h2h-pressure pressure-${pressureClass(pressure.level)}">
      <div><small>Change urgency</small><strong>${esc(pressure.level || 'LOW')}</strong></div>
      <div><h4>${esc(pressure.headline || 'Review matchup')}</h4><p>${esc(pressure.detail || '')}</p></div>
      ${bestMove ? `<button class="h2h-best-move" data-player-id="${esc(bestMove.add_player_id)}"><small>Best evidence-backed move</small><strong>Add ${esc(bestMove.add_player)} · Drop ${esc(bestMove.drop_player)}</strong><span>${esc(h2hSigned(bestMove.projected_points_delta))} projected pts · ${esc(h2hSigned(bestMove.roster_value_delta))} Roster Value</span></button>` : `<div class="h2h-best-move muted"><small>Best evidence-backed move</small><strong>No tactical swap clears the guardrails</strong></div>`}
    </div>

    <div class="h2h-scout-grid">
      <article><small>Opponent formation</small><strong>${esc(opponent.formation || '-')}</strong><span>Estimated legal XI</span></article>
      <article><small>Strongest group</small><strong>${esc(oppScout.strongest_group || '-')}</strong><span>By average Start Score</span></article>
      <article><small>Weakest group</small><strong>${esc(oppScout.weakest_group || '-')}</strong><span>Potential attack point</span></article>
      <article><small>Bench depth</small><strong>${esc(oppScout.bench_depth || '-')}</strong><span>Bench Start ${esc(h2hScore(oppScout.bench_start_score))}</span></article>
      <article><small>Role uncertainty</small><strong>${esc(oppScout.non_high_evidence_starters ?? '-')}</strong><span>Likely starters below HIGH evidence</span></article>
      <article><small>Availability concerns</small><strong>${esc(oppScout.availability_concerns ?? '-')}</strong><span>Squad players below 75 availability</span></article>
      <article class="wide"><small>Weakest likely starter</small><strong>${scoutWeakStarter(oppScout.weakest_starter)}</strong></article>
    </div>

    <div class="h2h-secondary-edges">
      <span><small>Start Score edge</small><strong>${esc(h2hSigned(matchup.start_score_edge))}</strong></span>
      <span><small>Roster-value edge</small><strong>${esc(h2hSigned(matchup.roster_value_edge))}</strong></span>
      <span><small>Fixture edge</small><strong>${esc(h2hSigned(matchup.fixture_edge))}</strong></span>
      <span><small>Model evidence</small><strong>${esc(matchup.evidence || 'LOW')}</strong></span>
    </div>

    <div class="h2h-section-head"><div><h3>Where the matchup is won</h3><p>Projected-point differences show the estimated GW contribution by position; Start Score remains useful for lineup confidence.</p></div></div>
    <div class="h2h-position-grid">${positions.map(row => `<article class="h2h-position-card ${h2hSignalClass(row.signal)}"><div><strong>${esc(row.position)}</strong><span>${esc(row.signal)}</span></div><div class="h2h-position-main"><small>Projected edge</small><b>${esc(h2hSigned(row.projected_points_edge))}</b></div><div class="h2h-position-sub"><span>You ${esc(h2hScore(row.my_projected_points))}</span><span>Opp ${esc(h2hScore(row.opponent_projected_points))}</span><span>Start ${esc(h2hSigned(row.start_score_edge))}</span></div></article>`).join('')}</div>

    <div class="h2h-lineups">
      <section><div class="h2h-section-head"><div><h3>Your likely XI</h3><p>${esc(mine.formation || '-')} · ${esc(h2hScore(myProjection.total))} projected points.</p></div></div><div class="h2h-player-list">${myLineup.map(player => h2hPlayerRow(player, mine)).join('')}</div></section>
      <section><div class="h2h-section-head"><div><h3>Opponent likely XI</h3><p>${esc(opponent.formation || '-')} · ${esc(h2hScore(opponentProjection.total))} projected points. Estimated from their owned 15.</p></div></div><div class="h2h-player-list">${opponentLineup.map(player => h2hPlayerRow(player, opponent)).join('')}</div></section>
    </div>

    <div class="h2h-section-head"><div><h3>Threats and counterweights</h3><p>The assets most likely to shape the round, combining next-GW projection and longer-term roster quality.</p></div></div>
    <div class="h2h-threat-columns"><div><h4>Opponent threats</h4><div class="h2h-threat-grid">${threats.map(player => h2hThreatCard(player, 'THREAT')).join('')}</div></div><div><h4>Your counterweights</h4><div class="h2h-threat-grid">${counters.map(player => h2hThreatCard(player, 'EDGE ASSET')).join('')}</div></div></div>

    <div class="h2h-section-head"><div><h3>Tactical priorities</h3><p>Matchup-specific advice is constrained by the normal waiver engine and season-long Roster Value. A projected deficit alone cannot justify a destructive swap.</p></div></div>
    <div class="h2h-priority-grid">${priorities.map(h2hPriorityCard).join('')}</div>
    <div class="h2h-note">${esc(h2h.note || '')} Opponent manager identity is redacted from the public Pages dataset.</div>
  </section>`;
}

const v08Controls = controls;
controls = function() {
  if (VIEW === 'h2h') return '';
  return v08Controls();
};

const v08RenderPlanner = renderPlanner;
renderPlanner = function() {
  if (VIEW === 'h2h') return renderH2H();
  return v08RenderPlanner();
};

const v08AllPlayers = allPlayers;
allPlayers = function() {
  const base = v08AllPlayers();
  const opponent = DATA?.h2h_matchup?.opponent_squad || [];
  const byId = new Map(base.map(player => [String(player.player_id), player]));
  opponent.forEach(player => byId.set(String(player.player_id), player));
  return [...byId.values()];
};
