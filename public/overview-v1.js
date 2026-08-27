function overviewNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function overviewSigned(value) {
  const number = overviewNumber(value);
  return `${number > 0 ? '+' : ''}${number.toFixed(1)}`;
}

function overviewPriorityRank(priority) {
  return {critical: 3, important: 2, watch: 1}[priority] || 0;
}

function overviewRelevantUpdates(data) {
  const squadIds = new Set((data.my_squad || []).map(player => String(player.player_id)));
  const opponentIds = new Set((data.h2h_matchup?.opponent_squad || []).map(player => String(player.player_id)));
  const available = new Map((data.available_players || []).map(player => [String(player.player_id), player]));
  const supportedActions = new Set(['SWAP NOW', 'STASH SWAP', 'CONSIDER']);
  const rows = (data.change_feed?.items || []).filter(item => {
    if ((item.status || 'active') !== 'active' || !['critical', 'important'].includes(item.priority)) return false;
    const playerId = String(item.player_id ?? '');
    if (squadIds.has(playerId)) return true;
    if (opponentIds.has(playerId) && item.kind === 'transfer_update') return true;
    const candidate = available.get(playerId);
    return Boolean(candidate && supportedActions.has(candidate.replacement?.action));
  });
  const byPlayer = new Map();
  rows.forEach(item => {
    const key = item.player_id == null ? String(item.stream || item.event_id) : `player:${item.player_id}`;
    const previous = byPlayer.get(key);
    if (!previous || overviewPriorityRank(item.priority) > overviewPriorityRank(previous.priority)) {
      byPlayer.set(key, {
        key,
        priority: item.priority,
        badge: item.badge || 'UPDATE',
        title: item.title || 'Decision update',
        detail: item.detail || 'New evidence may affect the next decision.',
        view: 'changes',
        last_seen: item.last_seen,
      });
    }
  });
  return [...byPlayer.values()];
}

function overviewAvailabilityActions(data) {
  const dashboard = data.injury_stash || {};
  const actions = [];
  (dashboard.squad_health || []).forEach(row => {
    if (row.dashboard_action === 'REVIEW DROP') actions.push({
      key: `player:${row.player_id}`, priority: 'critical', badge: 'SQUAD', title: `${row.player}: review roster place`,
      detail: row.news || row.recommendation_reason || 'Availability now affects the roster decision.', view: 'injury',
    });
  });
  (dashboard.stash_candidates || []).forEach(row => {
    if (['SWAP NOW', 'STASH SWAP'].includes(row.dashboard_action)) actions.push({
      key: `player:${row.player_id}`, priority: 'important', badge: row.dashboard_action, title: `${row.player}: ${row.dashboard_action.toLowerCase()}`,
      detail: row.drop_player ? `Best comparison is ${row.player} for ${row.drop_player}.` : (row.news || 'A guarded stash move clears the action threshold.'), view: 'injury',
    });
  });
  (dashboard.transfer_watch || []).forEach(row => {
    if (row.context === 'YOUR SQUAD' && row.blocks_acquisition) actions.push({
      key: `player:${row.player_id}`, priority: 'critical', badge: 'TRANSFER', title: `${row.player}: ${row.dashboard_action || 'exit alert'}`,
      detail: row.transfer_summary || 'A reliable exit report changes the roster decision.', view: 'injury',
    });
    if (row.context === 'FREE AGENT' && row.dashboard_action === 'EARLY PICKUP') actions.push({
      key: `player:${row.player_id}`, priority: 'important', badge: 'EARLY PICKUP', title: `${row.player}: early-pickup window`,
      detail: row.transfer_summary || 'Destination fixtures and role evidence clear the early-pickup guardrails.', view: 'injury',
    });
  });
  return actions;
}

function overviewH2HAction(data) {
  const h2h = data.h2h_matchup || {};
  const pressure = h2h.matchup?.pressure || {};
  if (!h2h.available || !['HIGH', 'VERY HIGH'].includes(pressure.level)) return [];
  return [{
    key: 'h2h', priority: pressure.level === 'VERY HIGH' ? 'critical' : 'important',
    badge: 'H2H',
    title: pressure.headline || `${pressure.level} matchup pressure`,
    detail: pressure.detail || 'The next matchup warrants a decision review.',
    view: 'h2h',
  }];
}

function overviewUrgentItems(data) {
  const items = [
    ...overviewRelevantUpdates(data),
    ...overviewAvailabilityActions(data),
    ...overviewH2HAction(data),
  ];
  const health = snapshotHealth(data.generated_at);
  if (health.state === 'critical' || health.state === 'unknown') items.push({
    key: 'data-freshness', priority: 'critical', badge: 'DATA', title: 'Recommendations need a fresh collection',
    detail: health.state === 'unknown' ? 'The snapshot time cannot be verified.' : `The snapshot is ${snapshotAgeLabel(health.ageMs)} old.`,
    view: 'overview',
  });
  const deduplicated = new Map();
  items.forEach((item, index) => {
    const key = item.key || `item:${index}`;
    const previous = deduplicated.get(key);
    if (!previous || overviewPriorityRank(item.priority) > overviewPriorityRank(previous.priority)) deduplicated.set(key, item);
  });
  return [...deduplicated.values()].sort((a, b) => overviewPriorityRank(b.priority) - overviewPriorityRank(a.priority) || String(b.last_seen || '').localeCompare(String(a.last_seen || '')));
}

function overviewBestWaiver(data) {
  const priority = {'SWAP NOW': 4, 'STASH SWAP': 3, 'CONSIDER': 2, 'KEEP ROSTER': 1};
  return [...(data.available_players || [])]
    .filter(player => player.replacement)
    .sort((a, b) => (priority[b.replacement.action] || 0) - (priority[a.replacement.action] || 0)
      || overviewNumber(b.replacement.combined_delta, -999) - overviewNumber(a.replacement.combined_delta, -999))[0] || null;
}

function overviewHeroMarkup(data, urgent) {
  const scoringGw = data.current_gameweek;
  const decisionGw = data.decision_gameweek ?? data.planning_gameweeks?.[0] ?? scoringGw;
  const gwLabel = scoringGw === 0
    ? `Planning GW${esc(decisionGw || 1)}`
    : Number(scoringGw) === Number(decisionGw)
      ? `Decisions · GW${esc(decisionGw)}`
      : `Live GW${esc(scoringGw)} · Plan GW${esc(decisionGw)}`;
  const injury = data.injury_stash?.summary || {};
  const transfers = overviewNumber(injury.transfer_alerts);
  const h2h = data.h2h_matchup?.matchup || {};
  const status = urgent.length ? `${urgent.length} action${urgent.length === 1 ? '' : 's'} to review` : 'No urgent action';
  const statusClass = urgent.some(item => item.priority === 'critical') ? 'critical' : urgent.length ? 'important' : 'clear';
  return `<div class="hero-top overview-hero-top"><div><div class="eyebrow">${esc(data.league_name || 'Draft league')}</div><h2>Gameweek overview</h2><p>One screen for the decisions that matter now. Open a specialist view only when you need its evidence.</p></div><div class="gw-pill">${gwLabel}</div></div>
    <div id="freshness-warning-slot">${snapshotWarningMarkup(data)}</div>
    <div class="overview-status ${statusClass}"><span>${statusClass === 'clear' ? '✓' : '!'}</span><div><small>Priority check</small><strong>${esc(status)}</strong></div>${urgent.length ? `<button data-view-link="${esc(urgent[0].view)}">Review first action →</button>` : `<button data-view-link="squad">Review recommended XI →</button>`}</div>
    <div class="stats overview-stats"><div class="stat"><small>Urgent decisions</small><strong>${esc(urgent.length)}</strong></div><div class="stat"><small>Squad concerns</small><strong>${esc(injury.squad_concerns || 0)}</strong></div><div class="stat"><small>Transfer alerts</small><strong>${esc(transfers)}</strong></div><div class="stat"><small>Next H2H</small><strong>${esc(h2h.signal || '-')}</strong></div></div>`;
}

function overviewAlertCard(item) {
  return `<button class="overview-alert priority-${esc(item.priority || 'important')}" data-view-link="${esc(item.view || 'changes')}"><span>${esc(item.badge || 'ACTION')}</span><span class="overview-alert-copy"><strong>${esc(item.title)}</strong><small>${esc(item.detail)}</small></span><b>Open →</b></button>`;
}

function overviewPanel(title, eyebrow, body, view, tone = '') {
  return `<button class="overview-panel ${tone}" data-view-link="${esc(view)}"><span class="eyebrow">${esc(eyebrow)}</span><span class="overview-panel-title">${esc(title)}</span>${body}<b>Open ${esc(view === 'squad' ? 'My Team' : view === 'injury' ? 'Health & Transfers' : view === 'h2h' ? 'H2H' : view === 'available' ? 'Available' : 'view')} →</b></button>`;
}

function renderOverview(data) {
  const urgent = overviewUrgentItems(data);
  const lineup = data.recommended_lineup || {};
  const h2h = data.h2h_matchup || {};
  const matchup = h2h.matchup || {};
  const myProjection = matchup.my?.projection || {};
  const opponentProjection = matchup.opponent?.projection || {};
  const waiver = overviewBestWaiver(data);
  const injury = data.injury_stash?.summary || {};
  const outlook = data.h2h_outlook?.summary || {};
  const alerts = urgent.slice(0, 3);
  const alertSection = alerts.length
    ? `<section class="overview-priority"><div class="overview-section-head"><div><span class="eyebrow">Priority inbox</span><h3>Act before the next deadline</h3></div><button data-view-link="changes">All updates →</button></div><div class="overview-alerts">${alerts.map(overviewAlertCard).join('')}</div>${urgent.length > alerts.length ? `<small class="overview-more">${esc(urgent.length - alerts.length)} more relevant item${urgent.length - alerts.length === 1 ? '' : 's'} remain in the specialist views.</small>` : ''}</section>`
    : `<section class="overview-clear"><span>✓</span><div><strong>No urgent action clears the guardrails</strong><small>The toolkit will keep monitoring availability, waivers, transfers and matchup pressure.</small></div></section>`;
  const lineupBody = lineup.is_valid
    ? `<span class="overview-panel-summary"><strong>${esc(lineup.formation || '-')}</strong> recommended shape for GW${esc(lineup.gameweek || data.decision_gameweek || '-')}.</span><span>${esc(lineup.average_start_score ?? '-')} average Start Score · ${esc((lineup.close_calls || []).length)} close call${(lineup.close_calls || []).length === 1 ? '' : 's'}</span>`
    : '<span class="overview-panel-summary">Recommended XI is waiting for a complete legal squad snapshot.</span>';
  const h2hBody = h2h.available
    ? `<span class="overview-panel-summary"><strong>${esc(h2h.opponent?.display_name || 'League opponent')}</strong> · ${esc(matchup.signal || 'EVEN')} matchup.</span><span>Projected XI ${esc(myProjection.total ?? '-')}–${esc(opponentProjection.total ?? '-')} · ${esc(overviewSigned(matchup.projected_points_edge))} edge</span>`
    : '<span class="overview-panel-summary">The next opponent comparison is not available yet.</span>';
  const waiverBody = waiver
    ? `<span class="overview-panel-summary"><strong>${esc(waiver.replacement.action)}</strong> · Add ${esc(waiver.player)}${waiver.replacement.drop_player ? ` for ${esc(waiver.replacement.drop_player)}` : ''}.</span><span>${esc(overviewSigned(waiver.replacement.combined_delta))} combined heuristic · ${esc(waiver.replacement.confidence || 'LOW')} evidence</span>`
    : '<span class="overview-panel-summary">No supported same-position upgrade is available.</span>';
  const healthBody = `<span class="overview-panel-summary"><strong>${esc(injury.squad_concerns || 0)}</strong> squad concern${Number(injury.squad_concerns) === 1 ? '' : 's'} · <strong>${esc(injury.transfer_alerts || 0)}</strong> transfer alert${Number(injury.transfer_alerts) === 1 ? '' : 's'}.</span><span>${esc(injury.act_now || 0)} health/stash action${Number(injury.act_now) === 1 ? '' : 's'} clear the act-now threshold.</span>`;
  const outlookBody = outlook.available_gameweeks
    ? `<span class="overview-panel-summary"><strong>${esc(outlook.signals?.EDGE || 0)} edge</strong> · ${esc(outlook.signals?.EVEN || 0)} even · ${esc(outlook.signals?.TRAIL || 0)} trail.</span><span>${esc(overviewSigned(outlook.projected_net))} projected four-GW net · weakest ${esc(outlook.recurring_weakness?.position || 'none')}</span>`
    : '<span class="overview-panel-summary">The four-Gameweek matchup outlook is pending.</span>';
  return `<div class="overview-dashboard">${alertSection}<section><div class="overview-section-head"><div><span class="eyebrow">At a glance</span><h3>Your decision surfaces</h3></div></div><div class="overview-grid">
    ${overviewPanel('Recommended XI', 'My Team', lineupBody, 'squad')}
    ${overviewPanel('Next opponent', 'H2H', h2hBody, 'h2h')}
    ${overviewPanel('Best supported move', 'Waivers', waiverBody, 'available')}
    ${overviewPanel('Health & transfer alerts', 'Player status', healthBody, 'injury')}
    ${overviewPanel('Four-Gameweek shape', 'Outlook', outlookBody, 'h2h')}
  </div></section></div>`;
}

function overviewViewMeta(view, data) {
  const gameweek = data.decision_gameweek ?? data.planning_gameweeks?.[0] ?? data.current_gameweek ?? '-';
  return {
    squad: ['My Team', `Official picks and the toolkit's separate recommended XI for GW${gameweek}.`],
    available: ['Available players', 'Compare free agents with your weakest same-position roster option.'],
    activity: ['League activity', 'Ownership changes detected between collector snapshots.'],
    planner: ['Four-Gameweek planner', `Fixture planning from GW${gameweek} without changing the active-round forecast.`],
  }[view];
}

const overviewBaseRender = render;
render = function() {
  overviewBaseRender();
  if (!DATA) return;
  const hero = document.getElementById('hero');
  const content = document.getElementById('content');
  const controlsSlot = document.getElementById('controls');
  if (VIEW === 'overview') {
    const urgent = overviewUrgentItems(DATA);
    hero.hidden = false;
    hero.className = 'hero overview-hero';
    hero.innerHTML = overviewHeroMarkup(DATA, urgent);
    controlsSlot.innerHTML = '';
    content.innerHTML = renderOverview(DATA);
    bindControls();
    bindPlayers();
    return;
  }
  const meta = overviewViewMeta(VIEW, DATA);
  if (meta) {
    hero.hidden = false;
    hero.className = 'hero compact-view-hero';
    hero.innerHTML = `<div><span class="eyebrow">${esc(DATA.league_name || 'Draft league')}</span><h2>${esc(meta[0])}</h2><p>${esc(meta[1])}</p></div>`;
  } else {
    hero.hidden = true;
    hero.className = 'hero';
    hero.innerHTML = '';
  }
};
