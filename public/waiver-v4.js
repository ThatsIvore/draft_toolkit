const replacementPriority = {'SWAP NOW': 4, 'STASH SWAP': 3, 'CONSIDER': 2, 'KEEP ROSTER': 1};

function signed(value) {
  const n = Number(value || 0);
  return `${n > 0 ? '+' : ''}${n.toFixed(1)}`;
}

function replacementSummary(p) {
  const r = p.replacement;
  if (!r) return '';
  return `<div class="swap-summary ${r.combined_delta > 0 ? 'positive' : ''}">
    <span>Overall ${signed(r.combined_delta)} · Floor ${signed(r.floor_delta)} · Upside ${signed(r.upside_delta)} · Evidence ${esc(r.confidence || 'LOW')}</span>
  </div>`;
}

function standaloneStrength(p) {
  const action = p.intelligence?.recommendation;
  if (!action) return '';
  if (action === 'CLAIM') return 'Strong';
  if (action === 'STASH') return 'Future value';
  if (action === 'WATCH') return 'Watch';
  if (action === 'PASS') return 'Depth';
  return action === 'HOLD' ? 'Strong' : 'Review';
}

function playerGrade(p) {
  const intel = p.intelligence || {};
  const strength = standaloneStrength(p);
  if (!strength) return '';
  return `<div class="decision-line secondary-grade"><span class="decision-reason">Standalone strength: <strong>${esc(strength)}</strong> · ${esc(intel.recommendation_reason || '')}</span></div>`;
}

function replacementBadge(action) {
  const mapped = action === 'SWAP NOW' ? 'CLAIM' : action === 'STASH SWAP' ? 'STASH' : action === 'CONSIDER' ? 'WATCH' : 'PASS';
  return `<span class="recommendation ${recommendationClass(mapped)}">${esc(action || 'KEEP ROSTER')}</span>`;
}

intelligenceStrip = function(p) {
  const intel = p.intelligence || {};
  if (intel.roster_score == null) return '<div class="placeholder-score">Intelligence pending next collection</div>';
  const primary = p.replacement
    ? `<div class="decision-line">${replacementBadge(p.replacement.action)}<span class="decision-reason">${esc(`Best swap: ${p.player} for ${p.replacement.drop_player}`)}</span></div>${playerGrade(p)}`
    : `<div class="decision-line">${recommendationBadge(intel)}<span class="decision-reason">${esc(intel.recommendation_reason || '')}</span></div>`;
  return `${primary}
    <div class="score-strip">
      <span class="score ${scoreClass(intel.roster_score)}"><small>Roster</small><strong>${esc(intel.roster_score)}</strong></span>
      <span class="score ${scoreClass(intel.floor_score)}"><small>Floor</small><strong>${esc(intel.floor_score ?? '-')}</strong></span>
      <span class="score ${scoreClass(intel.upside_score)}"><small>Upside</small><strong>${esc(intel.upside_score ?? '-')}</strong></span>
      <span class="score ${scoreClass(intel.fixture_score)}"><small>Fixtures</small><strong>${esc(intel.fixture_score)}</strong></span>
      ${intel.role_evidence == null ? '' : `<span class="score"><small>Role evidence</small><strong>${esc(intel.role_evidence)}</strong></span>`}
    </div>${replacementSummary(p)}`;
};

controls = function() {
  if (VIEW === 'activity') return '';
  if (VIEW === 'squad') return `<div class="view-toggle"><button data-squad-mode="pitch" class="${SQUAD_MODE==='pitch'?'active':''}">Pitch View</button><button data-squad-mode="list" class="${SQUAD_MODE==='list'?'active':''}">List View</button></div>`;
  return `<input id="search" class="search" type="search" placeholder="Search player or club" value="${esc(QUERY)}">
    <select id="position"><option value="ALL">All positions</option>${['GKP','DEF','MID','FWD'].map(p => `<option value="${p}" ${POS===p?'selected':''}>${p}</option>`).join('')}</select>
    ${VIEW === 'available' ? `<select id="sort">
      <option value="swap" ${SORT==='swap'?'selected':''}>Sort: best roster upgrade</option>
      <option value="action" ${SORT==='action'?'selected':''}>Sort: recommended action</option>
      <option value="roster" ${SORT==='roster'?'selected':''}>Sort: roster score</option>
      <option value="upside" ${SORT==='upside'?'selected':''}>Sort: upside</option>
      <option value="floor" ${SORT==='floor'?'selected':''}>Sort: floor</option>
      <option value="stash" ${SORT==='stash'?'selected':''}>Sort: stash score</option>
      <option value="fixtures" ${SORT==='fixtures'?'selected':''}>Sort: fixtures</option>
      <option value="points" ${SORT==='points'?'selected':''}>Sort: points</option>
      <option value="availability" ${SORT==='availability'?'selected':''}>Sort: fitness</option>
      <option value="name" ${SORT==='name'?'selected':''}>Sort: name</option>
    </select>` : ''}`;
};

renderAvailable = function() {
  let list = filtered(DATA.available_players || []);
  const score = (p,key) => Number(p.intelligence?.[key] || 0);
  if (SORT === 'swap') list.sort((a,b) => Number(b.replacement?.combined_delta ?? -999) - Number(a.replacement?.combined_delta ?? -999));
  if (SORT === 'action') list.sort((a,b) => {
    const actionDelta = (replacementPriority[b.replacement?.action] || 0) - (replacementPriority[a.replacement?.action] || 0);
    return actionDelta || Number(b.replacement?.combined_delta || 0) - Number(a.replacement?.combined_delta || 0) || score(b,'stash_score') - score(a,'stash_score');
  });
  if (SORT === 'roster') list.sort((a,b) => score(b,'roster_score') - score(a,'roster_score'));
  if (SORT === 'upside') list.sort((a,b) => score(b,'upside_score') - score(a,'upside_score'));
  if (SORT === 'floor') list.sort((a,b) => score(b,'floor_score') - score(a,'floor_score'));
  if (SORT === 'stash') list.sort((a,b) => score(b,'stash_score') - score(a,'stash_score'));
  if (SORT === 'fixtures') list.sort((a,b) => score(b,'fixture_score') - score(a,'fixture_score'));
  if (SORT === 'points') list.sort((a,b) => (b.total_points || 0) - (a.total_points || 0));
  if (SORT === 'availability') list.sort((a,b) => (b.chance_next_round ?? 100) - (a.chance_next_round ?? 100));
  if (SORT === 'name') list.sort((a,b) => String(a.player).localeCompare(String(b.player)));
  const shown = list.slice(0,100);
  return shown.length ? `<div class="group-title"><h3>Available players</h3><span class="count">Showing ${shown.length} of ${list.length}</span></div><div class="player-list">${shown.map(p => playerCard(p,'AVAILABLE')).join('')}</div>` : '<div class="empty">No available players match these filters.</div>';
};

const v3OpenPlayer = openPlayer;
openPlayer = function(id) {
  v3OpenPlayer(id);
  const p = allPlayers().find(x => String(x.player_id) === String(id));
  if (!p?.replacement) return;
  const r = p.replacement;
  const intel = p.intelligence || {};
  const body = document.querySelector('#player-drawer .drawer-body');
  if (!body) return;

  const panel = document.createElement('div');
  panel.className = 'drawer-section swap-panel';
  panel.innerHTML = `<strong>Waiver replacement check · v0.5.3</strong>
    <div class="swap-head"><b>${esc(r.action)}</b><span>Add ${esc(p.player)} · Drop ${esc(r.drop_player)} · ${esc(r.confidence || 'LOW')} confidence</span></div>
    <div class="model-grid"><span>Combined delta <b>${signed(r.combined_delta)}</b></span><span>Immediate delta <b>${signed(r.immediate_delta)}</b></span><span>Floor delta <b>${signed(r.floor_delta)}</b></span><span>Upside delta <b>${signed(r.upside_delta)}</b></span><span>4-GW roster delta <b>${signed(r.roster_delta)}</b></span><span>Future delta <b>${signed(r.future_delta)}</b></span></div>
    <div class="model-note">The model preserves a preseason 2025/26 performance prior and gradually blends in 2026/27 evidence as minutes accumulate. Role evidence is intentionally categorical rather than a pseudo-precise next-match probability.</div>`;
  body.prepend(panel);

  const drawerDecision = body.querySelector('.drawer-decision');
  if (drawerDecision) {
    const strength = standaloneStrength(p);
    drawerDecision.innerHTML = `${replacementBadge(r.action)}<strong>${esc(`Best swap: ${p.player} for ${r.drop_player}`)}</strong><span class="decision-reason">Standalone strength: <strong>${esc(strength || 'Review')}</strong>${intel.recommendation_reason ? ` · ${esc(intel.recommendation_reason)}` : ''}</span>`;
  }

  body.querySelectorAll('.decision-line').forEach(line => line.remove());
  const duplicateSummary = body.querySelector('.swap-summary');
  if (duplicateSummary) duplicateSummary.remove();

  const usage = body.querySelector('.usage-panel');
  if (usage) usage.innerHTML = `<div><small>Role evidence</small><strong>${esc(intel.role_evidence ?? '-')}</strong></div><div><small>Expected minutes heuristic</small><strong>${esc(intel.expected_minutes ?? '-')}</strong></div>`;
  if (usage) usage.insertAdjacentHTML('afterend', `<div class="usage-panel"><div><small>Floor</small><strong>${esc(intel.floor_score ?? '-')}</strong></div><div><small>Upside</small><strong>${esc(intel.upside_score ?? '-')}</strong></div><div><small>Sample confidence</small><strong>${esc(intel.sample_confidence ?? '-')}%</strong></div><div><small>Pts / 90</small><strong>${esc(intel.points_per_90 ?? '-')}</strong></div></div>`);
};
