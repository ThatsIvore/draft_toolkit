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

function h2hDecisionProfile(profile, compact = false) {
  const threat = profile?.decision_threat || {};
  const draft = profile?.draft || {};
  const management = profile?.management || {};
  if (!profile || !threat.level) return '';
  if (compact) {
    return `<span class="h2h-decision-chip threat-${pressureClass(threat.level)}">${esc(threat.level)} decision threat · ${esc(threat.evidence || 'LOW')} evidence</span>`;
  }
  const transferValue = management.average_transfer_value == null ? 'Pending' : h2hSigned(management.average_transfer_value);
  const lineupEfficiency = management.average_lineup_efficiency == null ? 'Pending' : `${h2hScore(management.average_lineup_efficiency)}%`;
  return `<section class="h2h-manager-profile threat-${pressureClass(threat.level)}">
    <div><small>Opponent decision profile</small><strong>${esc(threat.level)} threat</strong><span>${esc(threat.evidence || 'LOW')} live-decision evidence</span></div>
    <div><small>Draft prior</small><strong>${draft.score == null ? 'Unmapped' : h2hScore(draft.score)}</strong><span>${draft.resolved_picks == null ? 'No draft data' : `${esc(draft.resolved_picks)}/${esc(draft.total_picks)} picks resolved`}</span></div>
    <div><small>Transfer value</small><strong>${esc(transferValue)}</strong><span>${esc(management.transaction_windows || 0)} observed decision windows</span></div>
    <div><small>Lineup efficiency</small><strong>${esc(lineupEfficiency)}</strong><span>${esc(management.lineup_gameweeks || 0)} completed Gameweeks</span></div>
    <p>Future-GW adjustment ${esc(h2hSigned(threat.projected_points_adjustment || 0))} pts. Draft quality is a small early prior; actual transfers and submitted lineups gradually replace it.</p>
  </section>`;
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

function h2hDisclosure(index, title, detail, content, tone) {
  return `<details class="h2h-disclosure tone-${esc(tone)}">
    <summary><span class="h2h-disclosure-index">${esc(index)}</span><span class="h2h-disclosure-title"><strong>${esc(title)}</strong><small>${esc(detail)}</small></span><span class="h2h-disclosure-action">Explore</span></summary>
    <div class="h2h-disclosure-body">${content}</div>
  </details>`;
}

function scoutWeakStarter(row) {
  if (!row) return 'None identified';
  return `${esc(row.player)} · ${esc(row.position)} · ${esc(h2hScore(row.projected_points))} proj.`;
}

function h2hOutcomePanel() {
  const current = DATA?.outcome_diagnostics?.current;
  if (!current || current.phase === 'UNKNOWN') return '';
  const forecast = current.forecast || {};
  const recommended = forecast.recommended || {};
  const actual = current.actual || {};
  const evaluation = current.evaluation || {};
  const liveOrFinal = ['LIVE','FINAL'].includes(current.phase);
  const estimatedScore = actual.h2h_score_source === 'estimated_lineups';
  const phaseLabel = current.phase === 'FINAL' ? (estimatedScore ? 'Final score pending' : 'Final result') : current.phase === 'LIVE' ? (estimatedScore ? 'Estimated live score' : 'Live score') : 'Forecast locked';
  const eligibility = forecast.calibration_eligible ? 'Pre-GW calibration sample' : 'Mid-GW transparency sample';
  const sourceLabel = estimatedScore ? 'official XI vs opponent likely XI' : 'Draft league score';
  const resultLine = liveOrFinal
    ? `<strong>${esc(h2hScore(actual.h2h_my_points))}–${esc(h2hScore(actual.h2h_opponent_points))}</strong><span>${esc(actual.h2h_result || '-')} · ${esc(sourceLabel)}</span>`
    : `<strong>${esc(h2hScore((forecast.h2h || {}).projected_my_total))}–${esc(h2hScore((forecast.h2h || {}).projected_opponent_total))}</strong><span>projected</span>`;
  const error = current.phase === 'FINAL' && evaluation.recommended_absolute_error != null
    ? `<span>Absolute error ${esc(h2hScore(evaluation.recommended_absolute_error))}${evaluation.calibration_eligible ? '' : ' · excluded from calibration'}</span>`
    : `<span>${esc(eligibility)}</span>`;
  return `<section class="h2h-outcome">
    <div><small>${esc(phaseLabel)} · GW${esc(current.gameweek)}</small>${resultLine}</div>
    <div><small>Toolkit Recommended XI</small><strong>${liveOrFinal ? esc(h2hScore(actual.recommended_points)) : esc(h2hScore(recommended.projected_total))}</strong><span>${esc(h2hScore(recommended.projected_total))} forecast · ${esc(h2hScore(recommended.range_low))}–${esc(h2hScore(recommended.range_high))} band</span>${error}</div>
    <div><small>Official submitted XI</small><strong>${liveOrFinal && actual.official_points != null ? esc(h2hScore(actual.official_points)) : 'Pending'}</strong><span>${liveOrFinal ? 'current FPL Draft points' : 'available after the deadline'}</span></div>
  </section>`;
}

function h2hOutlookCard(card) {
  if (!card?.available) {
    return `<article class="h2h-outlook-card unavailable"><div class="h2h-outlook-head"><strong>GW${esc(card?.gameweek || '-')}</strong><span>UNAVAILABLE</span></div><p>${esc(card?.reason || 'No exact schedule projection is available.')}</p></article>`;
  }
  const mine = card.my || {};
  const opponent = card.opponent_projection || {};
  const opponentMeta = card.opponent || {};
  const weakness = card.weakest_position || {};
  const threat = card.key_threat || {};
  const profile = card.opponent_profile || {};
  const source = card.projection_source === 'frozen_gameweek_forecast'
    ? 'Frozen current-GW forecast'
    : card.projection_source === 'current_roster_plus_decision_profile'
      ? `Current roster · ${h2hSigned(card.decision_adjustment)} decision adjustment`
      : 'Current-roster projection';
  return `<article class="h2h-outlook-card ${h2hSignalClass(card.signal)}">
    <div class="h2h-outlook-head"><strong>GW${esc(card.gameweek)}</strong><span>${esc(card.signal || 'EVEN')}</span></div>
    <div class="h2h-outlook-opponent"><small>Opponent</small><strong>${esc(opponentMeta.display_name || 'League opponent')}</strong><span>${opponentMeta.rank != null ? `Rank #${esc(opponentMeta.rank)}` : 'Rank pending'}</span>${h2hDecisionProfile(profile, true)}</div>
    <div class="h2h-outlook-score"><span><small>You</small><strong>${esc(h2hScore(mine.total))}</strong></span><b>${esc(h2hSigned(card.projected_edge))}</b><span><small>Opponent</small><strong>${esc(h2hScore(opponent.total))}</strong></span></div>
    <div class="h2h-outlook-ranges"><span>${esc(h2hScore(mine.range_low))}–${esc(h2hScore(mine.range_high))}</span><small>uncertainty bands</small><span>${esc(h2hScore(opponent.range_low))}–${esc(h2hScore(opponent.range_high))}</span></div>
    <div class="h2h-outlook-detail"><span><small>Pressure point</small><strong>${esc(weakness.position || '-')} ${weakness.projected_points_edge != null ? h2hSigned(weakness.projected_points_edge) : ''}</strong></span><span><small>Key threat</small><strong>${esc(threat.player || '-')}</strong></span></div>
    <small class="h2h-outlook-source">${esc(source)} · ${esc(mine.formation || '-')} vs ${esc(opponent.formation || '-')}</small>
  </article>`;
}

function renderH2HOutlook() {
  const outlook = DATA?.h2h_outlook;
  if (!outlook?.gameweeks?.length) return '';
  const summary = outlook.summary || {};
  const signals = summary.signals || {};
  const toughest = summary.toughest_matchup || {};
  const best = summary.best_opportunity || {};
  const weakness = summary.recurring_weakness || {};
  return `<section class="h2h-outlook-shell">
    <div class="h2h-section-head"><div><div class="eyebrow">Four-Gameweek H2H Outlook · v1.1</div><h3>See the schedule before it becomes urgent</h3><p>Every card starts with the next actionable Gameweek and uses current rosters. The locked live round remains above in outcome tracking.</p></div></div>
    <div class="h2h-outlook-summary">
      <span class="tone-schedule"><small>Schedule shape</small><strong>${esc(signals.EDGE || 0)} edge · ${esc(signals.EVEN || 0)} even · ${esc(signals.TRAIL || 0)} trail</strong></span>
      <span class="tone-total"><small>Projected four-GW total</small><strong>${esc(h2hScore(summary.projected_for))}–${esc(h2hScore(summary.projected_against))}</strong></span>
      <span class="tone-tough"><small>Toughest matchup</small><strong>${toughest.gameweek ? `GW${esc(toughest.gameweek)} · ${esc(h2hSigned(toughest.projected_edge))}` : '-'}</strong></span>
      <span class="tone-best"><small>Best opportunity</small><strong>${best.gameweek ? `GW${esc(best.gameweek)} · ${esc(h2hSigned(best.projected_edge))}` : '-'}</strong></span>
      <span class="tone-weakness"><small>Recurring weakness</small><strong>${weakness.position ? `${esc(weakness.position)} · ${esc(h2hSigned(weakness.average_projected_edge))}` : 'None identified'}</strong></span>
    </div>
    <small class="h2h-swipe-hint">Swipe to explore every Gameweek →</small>
    <div class="h2h-outlook-grid">${outlook.gameweeks.map(h2hOutlookCard).join('')}</div>
    <div class="h2h-note">${esc(outlook.note || '')}</div>
  </section>`;
}

function renderH2H() {
  const h2h = DATA.h2h_matchup;
  if (!h2h || !h2h.available) {
    return `<section class="h2h-v08"><div class="h2h-empty"><div class="eyebrow">H2H Scout · v1.2</div><h3>Opponent comparison unavailable</h3><p>${esc(h2h?.reason || 'The current league payload did not expose enough H2H matchup data yet.')}</p></div>${renderH2HOutlook()}</section>`;
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
  const opponentProfile = h2h.opponent_profile || {};
  const opponentName = opponentMeta.display_name || 'League opponent';
  const rank = opponentMeta.rank != null ? `Rank #${esc(opponentMeta.rank)}` : 'Preseason rank pending';
  const myLineup = h2h.my_lineup?.starters || [];
  const opponentLineup = h2h.opponent_lineup?.starters || [];
  const positions = matchup.position_edges || [];
  const threats = h2h.opponent_threats || [];
  const counters = h2h.my_counterweights || [];
  const priorities = h2h.tactical_priorities || [];
  const scoutDetails = `${h2hDecisionProfile(opponentProfile)}<div class="h2h-scout-grid">
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
    <div class="h2h-position-grid">${positions.map(row => `<article class="h2h-position-card ${h2hSignalClass(row.signal)}"><div><strong>${esc(row.position)}</strong><span>${esc(row.signal)}</span></div><div class="h2h-position-main"><small>Projected edge</small><b>${esc(h2hSigned(row.projected_points_edge))}</b></div><div class="h2h-position-sub"><span>You ${esc(h2hScore(row.my_projected_points))}</span><span>Opp ${esc(h2hScore(row.opponent_projected_points))}</span><span>Start ${esc(h2hSigned(row.start_score_edge))}</span></div></article>`).join('')}</div>`;
  const lineupDetails = `<div class="h2h-lineups">
      <section><div class="h2h-section-head"><div><h3>Your likely XI</h3><p>${esc(mine.formation || '-')} · ${esc(h2hScore(myProjection.total))} projected points.</p></div></div><div class="h2h-player-list">${myLineup.map(player => h2hPlayerRow(player, mine)).join('')}</div></section>
      <section><div class="h2h-section-head"><div><h3>Opponent likely XI</h3><p>${esc(opponent.formation || '-')} · ${esc(h2hScore(opponentProjection.total))} projected points. Estimated from their owned 15.</p></div></div><div class="h2h-player-list">${opponentLineup.map(player => h2hPlayerRow(player, opponent)).join('')}</div></section>
    </div>`;
  const tacticalDetails = `<div class="h2h-section-head"><div><h3>Threats and counterweights</h3><p>The assets most likely to shape the round, combining next-GW projection and longer-term roster quality.</p></div></div>
    <div class="h2h-threat-columns"><div><h4>Opponent threats</h4><div class="h2h-threat-grid">${threats.map(player => h2hThreatCard(player, 'THREAT')).join('')}</div></div><div><h4>Your counterweights</h4><div class="h2h-threat-grid">${counters.map(player => h2hThreatCard(player, 'EDGE ASSET')).join('')}</div></div></div>
    <div class="h2h-section-head"><div><h3>Tactical priorities</h3><p>Matchup-specific advice is constrained by the normal waiver engine and season-long Roster Value. A projected deficit alone cannot justify a destructive swap.</p></div></div>
    <div class="h2h-priority-grid">${priorities.map(h2hPriorityCard).join('')}</div>
    <div class="h2h-note">${esc(h2h.note || '')} The public dashboard shows the manager's chosen team name while keeping real names and internal identifiers private.</div>`;
  return `<section class="h2h-v08 h2h-v10">
    <div class="h2h-intro h2h-hero">
      <div class="h2h-hero-copy"><div class="eyebrow">H2H Scout · v1.3 · GW${esc(h2h.gameweek)}</div><h3>Scout the next matchup.<br><span>Keep the decision simple.</span></h3><p>Advice is centred on GW${esc(h2h.gameweek)}, the first matchup you can still influence. Open the deeper sections only when you need the evidence behind it.</p><div class="h2h-hero-tags"><span>${esc(matchup.signal || 'EVEN')} matchup</span><span>${esc(matchup.evidence || 'LOW')} evidence</span>${opponentProfile?.decision_threat?.level ? `<span>${esc(opponentProfile.decision_threat.level)} decision threat</span>` : ''}</div></div>
      <div class="h2h-opponent"><small>Upcoming opponent</small><strong>${esc(opponentName)}</strong><span>${rank}${opponentMeta.h2h_points != null ? ` · ${esc(opponentMeta.h2h_points)} H2H pts` : ''}</span>${h2hDecisionProfile(opponentProfile, true)}</div>
    </div>

    ${h2hOutcomePanel()}

    ${renderH2HOutlook()}

    <section class="h2h-current-decision">
      <div class="h2h-section-head"><div><div class="eyebrow">Next actionable Gameweek · GW${esc(h2h.gameweek)}</div><h3>The one matchup call that matters now</h3></div></div>
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
    </section>

    <div class="h2h-detail-stack">
      ${h2hDisclosure('01', 'Opponent scout & position matchups', 'Formation, squad profile and where the projected edge sits.', scoutDetails, 'violet')}
      ${h2hDisclosure('02', 'Likely starting lineups', 'Compare both projected XIs player by player.', lineupDetails, 'cyan')}
      ${h2hDisclosure('03', 'Threats & tactical priorities', 'Key assets, counterweights and guarded actions.', tacticalDetails, 'green')}
    </div>
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
