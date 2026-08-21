function availabilityBadge(p) {
  const chance = p.chance_next_round;
  if (chance == null || Number(chance) >= 100) return '<span class="badge good">Fit</span>';
  if (Number(chance) <= 0) return '<span class="badge bad">Unavailable</span>';
  if (Number(chance) >= 75) return `<span class="badge warn">${esc(chance)}% fit</span>`;
  return `<span class="badge bad">${esc(chance)}% fit</span>`;
}

function intelligenceStrip(p) {
  const intel = p.intelligence || {};
  if (intel.roster_score == null) return '<div class="placeholder-score">Intelligence pending next collection</div>';
  return `<div class="score-strip">
    <span class="score ${scoreClass(intel.roster_score)}"><small>Roster</small><strong>${esc(intel.roster_score)}</strong></span>
    <span class="score ${scoreClass(intel.stash_score)}"><small>Stash</small><strong>${esc(intel.stash_score)}</strong></span>
    <span class="score ${scoreClass(intel.fixture_score)}"><small>Fixtures</small><strong>${esc(intel.fixture_score)}</strong></span>
    ${intel.start_probability == null ? '' : `<span class="score ${scoreClass(intel.start_probability)}"><small>Start</small><strong>${esc(intel.start_probability)}%</strong></span>`}
  </div>`;
}

function returnSignalBadge(intel) {
  const signal = intel?.injury_return_signal;
  if (signal === 'near-return') return '<span class="badge warn">Near return</span>';
  if (signal === 'return-watch') return '<span class="badge warn">Return watch</span>';
  if (signal === 'out') return '<span class="badge bad">Out</span>';
  return '';
}

function openPlayer(id) {
  const p = allPlayers().find(x => String(x.player_id) === String(id));
  if (!p) return;
  const intel = p.intelligence || {};
  const drawer = document.getElementById('player-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  drawer.innerHTML = `<div class="drawer-head"><button id="drawer-close" aria-label="Close">×</button><div class="eyebrow">${esc(p.position)} · ${esc(p.club || '-')}</div><h2>${esc(p.player)}</h2><div>${esc(p.total_points ?? 0)} points</div></div>
    <div class="drawer-body"><div class="badges">${availabilityBadge(p)}${returnSignalBadge(intel)}</div>${intelligenceStrip(p)}
    <div class="usage-panel"><div><small>Start probability</small><strong>${intel.start_probability == null ? '-' : `${esc(intel.start_probability)}%`}</strong></div><div><small>Expected minutes</small><strong>${intel.expected_minutes == null ? '-' : esc(intel.expected_minutes)}</strong></div></div>
    <div class="drawer-fixtures">${(p.fixtures || []).map(g => `<div class="drawer-fixture fdr-${gwDifficulty(g) || 3}"><strong>GW${g.gameweek}</strong><div>${esc(fixtureLabel(p,g.gameweek))}</div><small>Difficulty ${esc(gwDifficulty(g) || 3)}/5</small></div>`).join('')}</div>
    <div class="drawer-section"><strong>Latest status</strong><div class="news">${esc(p.news || 'No current player news')}</div></div>
    <div class="drawer-section"><strong>How v0.2 scores this player</strong><div class="model-grid"><span>Position baseline <b>${esc(intel.baseline_score ?? '-')}</b></span><span>4-GW fixtures <b>${esc(intel.fixture_score ?? '-')}</b></span><span>Usage <b>${esc(intel.usage_score ?? '-')}</b></span><span>Availability <b>${esc(intel.availability_score ?? '-')}</b></span></div><div class="model-note">Start probability and expected minutes are transparent proxies derived from public season starts/minutes and current FPL availability; they are not official forecasts. Roster value now includes usage alongside baseline, fixtures and availability. Stash value keeps more weight on future fixtures.</div></div></div>`;
  backdrop.hidden = false; drawer.classList.add('open'); drawer.setAttribute('aria-hidden','false');
  document.getElementById('drawer-close').addEventListener('click', closePlayer);
}
