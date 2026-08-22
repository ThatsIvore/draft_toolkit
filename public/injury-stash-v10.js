function injuryScore(value) {
  if (value == null || value === '') return '-';
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(1) : '-';
}

function injurySigned(value) {
  if (value == null || value === '') return '-';
  const number = Number(value);
  if (!Number.isFinite(number)) return '-';
  return `${number > 0 ? '+' : ''}${number.toFixed(1)}`;
}

function injuryActionClass(action) {
  if (['SWAP NOW', 'STASH SWAP', 'STASH'].includes(action)) return 'act';
  if (action === 'REVIEW DROP') return 'review';
  if (action === 'HOLD') return 'hold';
  if (action === 'NO MOVE') return 'quiet';
  return 'monitor';
}

function injuryReturnLabel(row) {
  if (row.expected_return_gameweek) {
    return `Expected ${esc(row.expected_return || 'date pending')} · around GW${esc(row.expected_return_gameweek)}`;
  }
  if (row.expected_return) return `Expected ${esc(row.expected_return)} · beyond current window`;
  if (row.health_signal === 'near-return') return 'Near return · no official date supplied';
  if (row.health_signal === 'return-watch') return 'Return watch · no official date supplied';
  return 'No official return date';
}

function injuryKit(row) {
  return recommendedKit({team_code: row.team_code, club: row.club, position: row.position}, true);
}

function healthDecisionCard(row, context) {
  const action = row.dashboard_action || 'MONITOR';
  const fixture = row.return_fixture;
  const drop = row.drop_player ? `<span class="injury-swap">Best comparison: ${esc(row.player)} for ${esc(row.drop_player)} · ${esc(injurySigned(row.combined_delta))}</span>` : '';
  return `<button class="injury-decision-card ${injuryActionClass(action)}" data-player-id="${esc(row.player_id)}">
    <div class="injury-card-top">${injuryKit(row)}<div><span class="injury-action">${esc(action)}</span><h4>${esc(row.player)}</h4><small>${esc(row.position)} · ${esc(row.club || '-')} · ${esc(context)}</small></div></div>
    <p>${esc(row.news || row.recommendation_reason || 'No current player news')}</p>
    <div class="injury-return"><strong>${injuryReturnLabel(row)}</strong>${fixture ? `<span>Return fixture: ${esc(fixture.label)} · FDR ${esc(fixture.difficulty ?? '-')}</span>` : ''}</div>
    <div class="injury-metrics"><span><small>Fitness</small><b>${esc(row.chance_next_round ?? 100)}%</b></span><span><small>Stash</small><b>${esc(injuryScore(row.stash_score))}</b></span><span><small>After return</small><b>${esc(injuryScore(row.post_return_fixture_score))}</b></span></div>
    ${drop}<span class="injury-open">Open player evidence →</span>
  </button>`;
}

function returnTimelineCard(row) {
  const fixture = row.return_fixture || {};
  return `<button class="return-timeline-card" data-player-id="${esc(row.player_id)}">
    <span class="return-gw">GW${esc(row.expected_return_gameweek)}</span>
    ${injuryKit(row)}
    <span class="return-player"><strong>${esc(row.player)}</strong><small>${esc(row.position)} · ${esc(row.club || '-')}</small></span>
    <span class="return-match"><small>First dated opportunity</small><strong>${esc(fixture.label || '-')}</strong></span>
    <span class="return-score"><small>After-return fixtures</small><strong>${esc(injuryScore(row.post_return_fixture_score))}</strong></span>
    <span class="injury-action ${injuryActionClass(row.dashboard_action)}">${esc(row.dashboard_action || 'NO MOVE')}</span>
  </button>`;
}

function injuryEmpty(title, detail) {
  return `<div class="injury-empty"><strong>${esc(title)}</strong><span>${esc(detail)}</span></div>`;
}

function renderInjuryStash() {
  const dashboard = DATA?.injury_stash;
  if (!dashboard?.available) {
    return `<section class="injury-dashboard">${injuryEmpty('Injury decisions pending', 'Run the next collection to build the return-aligned injury and stash dashboard.')}</section>`;
  }
  const summary = dashboard.summary || {};
  const squad = dashboard.squad_health || [];
  const candidates = dashboard.stash_candidates || [];
  const returns = dashboard.return_calendar || [];
  return `<section class="injury-dashboard">
    <header class="injury-hero">
      <div><div class="eyebrow">Injuries &amp; Stashes · ${esc(dashboard.model || 'v1.0')}</div><h3>Turn return timing into a decision</h3><p>Only the health updates that can affect your roster are surfaced here. Confirmed dates are matched to fixtures from the return Gameweek onward.</p></div>
      <span class="injury-hero-pill">${esc(summary.decision_count || 0)} decision${Number(summary.decision_count) === 1 ? '' : 's'}</span>
    </header>
    <div class="injury-summary">
      <span class="squad"><small>Your squad</small><strong>${esc(summary.squad_concerns || 0)} concern${Number(summary.squad_concerns) === 1 ? '' : 's'}</strong></span>
      <span class="act"><small>Act now</small><strong>${esc(summary.act_now || 0)} candidate${Number(summary.act_now) === 1 ? '' : 's'}</strong></span>
      <span class="monitor"><small>Monitor</small><strong>${esc(summary.monitor || 0)} candidate${Number(summary.monitor) === 1 ? '' : 's'}</strong></span>
      <span class="return"><small>Dated returns</small><strong>${esc(summary.dated_returns || 0)} in window</strong></span>
    </div>

    <section class="injury-section">
      <div class="injury-section-head"><div><span>01</span><h3>Your squad health</h3></div><p>Protect a valuable hold—or review the roster spot when near-term value has disappeared.</p></div>
      ${squad.length ? `<div class="injury-card-grid">${squad.map(row => healthDecisionCard(row, 'YOUR SQUAD')).join('')}</div>` : injuryEmpty('Squad health is clear', 'None of your 15 players currently has an official availability concern.')}
    </section>

    <section class="injury-section">
      <div class="injury-section-head"><div><span>02</span><h3>Stash radar</h3></div><p>Only free agents who clear an action or monitor guardrail appear—this is not the full injury list.</p></div>
      ${candidates.length ? `<div class="injury-card-grid">${candidates.map(row => healthDecisionCard(row, row.confidence ? `${row.confidence} EVIDENCE` : 'FREE AGENT')).join('')}</div>` : injuryEmpty('No stash move clears the guardrails', 'Current injured free agents do not justify a roster move or priority monitor alert.')}
    </section>

    <section class="injury-section return-section">
      <div class="injury-section-head"><div><span>03</span><h3>Return window</h3></div><p>Dated returns are shown only when they fall inside the current planning horizon and retain enough value to matter.</p></div>
      ${returns.length ? `<div class="return-timeline">${returns.map(returnTimelineCard).join('')}</div>` : injuryEmpty('No relevant dated return in GW window', 'Official news has not supplied a decision-relevant return date inside the current four-Gameweek horizon.')}
    </section>
    <div class="injury-note">${esc(dashboard.note || '')}</div>
  </section>`;
}

const injuryControls = controls;
controls = function() {
  if (VIEW === 'injury') return '';
  return injuryControls();
};

const injuryRenderPlanner = renderPlanner;
renderPlanner = function() {
  if (VIEW === 'injury') return renderInjuryStash();
  return injuryRenderPlanner();
};
