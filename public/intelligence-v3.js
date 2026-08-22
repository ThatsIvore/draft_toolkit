function recommendationClass(action) {
  if (action === 'CLAIM') return 'action-claim';
  if (action === 'STASH') return 'action-stash';
  if (action === 'HOLD') return 'action-hold';
  if (action === 'REVIEW DROP') return 'action-drop';
  if (action === 'PASS') return 'action-pass';
  return 'action-watch';
}

function recommendationBadge(intel) {
  const action = intel?.recommendation;
  if (!action) return '';
  return `<span class="recommendation ${recommendationClass(action)}">${esc(action)}</span>`;
}

function trendBadge(intel) {
  const trend = intel?.health_trend;
  if (trend === 'improving') return '<span class="badge good">Health improving</span>';
  if (trend === 'worsening') return '<span class="badge bad">Health worsening</span>';
  if (trend === 'news-changed') return '<span class="badge warn">New status update</span>';
  return '';
}

function intelligenceStrip(p) {
  const intel = p.intelligence || {};
  if (intel.roster_score == null) return '<div class="placeholder-score">Intelligence pending next collection</div>';
  return `<div class="decision-line">${recommendationBadge(intel)}<span class="decision-reason">${esc(intel.recommendation_reason || '')}</span></div>
    <div class="score-strip">
      <span class="score ${scoreClass(intel.roster_score)}"><small>Roster</small><strong>${esc(intel.roster_score)}</strong></span>
      <span class="score ${scoreClass(intel.stash_score)}"><small>Stash</small><strong>${esc(intel.stash_score)}</strong></span>
      <span class="score ${scoreClass(intel.fixture_score)}"><small>Fixtures</small><strong>${esc(intel.fixture_score)}</strong></span>
      ${intel.start_probability == null ? '' : `<span class="score ${scoreClass(intel.start_probability)}"><small>Start</small><strong>${esc(intel.start_probability)}%</strong></span>`}
    </div>`;
}

const actionPriority = {'CLAIM': 6, 'STASH': 5, 'WATCH': 4, 'HOLD': 3, 'REVIEW DROP': 2, 'PASS': 1};

function controls() {
  if (VIEW === 'activity') return '';
  if (VIEW === 'squad') return `<div class="view-toggle"><button data-squad-mode="pitch" class="${SQUAD_MODE==='pitch'?'active':''}">Pitch View</button><button data-squad-mode="list" class="${SQUAD_MODE==='list'?'active':''}">List View</button></div>`;
  return `<input id="search" class="search" type="search" placeholder="Search player or club" value="${esc(QUERY)}">
    <select id="position"><option value="ALL">All positions</option>${['GKP','DEF','MID','FWD'].map(p => `<option value="${p}" ${POS===p?'selected':''}>${p}</option>`).join('')}</select>
    ${VIEW === 'available' ? `<select id="sort">
      <option value="action" ${SORT==='action'?'selected':''}>Sort: recommended action</option>
      <option value="roster" ${SORT==='roster'?'selected':''}>Sort: roster score</option>
      <option value="stash" ${SORT==='stash'?'selected':''}>Sort: stash score</option>
      <option value="fixtures" ${SORT==='fixtures'?'selected':''}>Sort: fixtures</option>
      <option value="points" ${SORT==='points'?'selected':''}>Sort: points</option>
      <option value="availability" ${SORT==='availability'?'selected':''}>Sort: fitness</option>
      <option value="name" ${SORT==='name'?'selected':''}>Sort: name</option>
    </select>` : ''}`;
}

function renderAvailable() {
  let list = filtered(DATA.available_players || []);
  const score = (p,key) => Number(p.intelligence?.[key] || 0);
  if (SORT === 'action') list.sort((a,b) => {
    const actionDelta = (actionPriority[b.intelligence?.recommendation] || 0) - (actionPriority[a.intelligence?.recommendation] || 0);
    return actionDelta || score(b,'stash_score') - score(a,'stash_score');
  });
  if (SORT === 'roster') list.sort((a,b) => score(b,'roster_score') - score(a,'roster_score'));
  if (SORT === 'stash') list.sort((a,b) => score(b,'stash_score') - score(a,'stash_score'));
  if (SORT === 'fixtures') list.sort((a,b) => score(b,'fixture_score') - score(a,'fixture_score'));
  if (SORT === 'points') list.sort((a,b) => (b.total_points || 0) - (a.total_points || 0));
  if (SORT === 'availability') list.sort((a,b) => (b.chance_next_round ?? 100) - (a.chance_next_round ?? 100));
  if (SORT === 'name') list.sort((a,b) => String(a.player).localeCompare(String(b.player)));
  const shown = list.slice(0,100);
  return shown.length ? `<div class="group-title"><h3>Available players</h3><span class="count">Showing ${shown.length} of ${list.length}</span></div><div class="player-list">${shown.map(p => playerCard(p,'AVAILABLE')).join('')}</div>` : '<div class="empty">No available players match these filters.</div>';
}

function openPlayer(id) {
  const p = allPlayers().find(x => String(x.player_id) === String(id));
  if (!p) return;
  const intel = p.intelligence || {};
  const drawer = document.getElementById('player-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  const returnText = intel.expected_return
    ? `${esc(intel.expected_return)}${intel.expected_return_gameweek ? ` · around GW${esc(intel.expected_return_gameweek)}` : ''}`
    : 'No explicit return date in official FPL news';
  drawer.innerHTML = `<div class="drawer-head"><button id="drawer-close" aria-label="Close">×</button><div class="eyebrow">${esc(p.position)} · ${esc(p.club || '-')}</div><h2>${esc(p.player)}</h2><div>${esc(p.total_points ?? 0)} points</div></div>
    <div class="drawer-body"><div class="drawer-decision">${recommendationBadge(intel)}<strong>${esc(intel.recommendation_reason || '')}</strong></div>
    <div class="badges">${availabilityBadge(p)}${returnSignalBadge(intel)}${trendBadge(intel)}</div>
    ${intelligenceStrip(p)}
    <div class="usage-panel"><div><small>Start probability</small><strong>${intel.start_probability == null ? '-' : `${esc(intel.start_probability)}%`}</strong></div><div><small>Expected minutes</small><strong>${intel.expected_minutes == null ? '-' : esc(intel.expected_minutes)}</strong></div></div>
    <div class="return-panel"><small>Expected return</small><strong>${returnText}</strong><span>Health trend: ${esc((intel.health_trend || 'unknown').replaceAll('-', ' '))}</span></div>
    <div class="drawer-fixtures">${(p.fixtures || []).map(g => `<div class="drawer-fixture fdr-${gwDifficulty(g) || 3}"><strong>GW${g.gameweek}</strong><div>${esc(fixtureLabel(p,g.gameweek))}</div><small>Difficulty ${esc(gwDifficulty(g) || 3)}/5</small></div>`).join('')}</div>
    <div class="drawer-section"><strong>Latest status</strong><div class="news">${esc(p.news || 'No current player news')}</div></div>
    <div class="drawer-section"><strong>How v0.5.4 decides</strong><div class="model-grid"><span>Roster value <b>${esc(intel.roster_score ?? '-')}</b></span><span>Stash value <b>${esc(intel.stash_score ?? '-')}</b></span><span>Post-return fixtures <b>${esc(intel.post_return_fixture_score ?? '-')}</b></span><span>Availability <b>${esc(intel.availability_score ?? '-')}</b></span></div><div class="model-note">The stash case uses fixtures from the estimated return Gameweek onward when official FPL news provides a readable date. Fixtures before that return are not credited, and the toolkit never invents a recovery date.</div></div></div>`;
  backdrop.hidden = false; drawer.classList.add('open'); drawer.setAttribute('aria-hidden','false');
  document.getElementById('drawer-close').addEventListener('click', closePlayer);
}
