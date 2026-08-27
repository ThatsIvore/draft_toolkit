const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

let DATA = null;
let VIEW = 'overview';
let SQUAD_MODE = 'pitch';
let QUERY = '';
let POS = 'ALL';
let SORT = 'roster';

const STALE_AFTER_MS = 6 * 60 * 60 * 1000;
const CRITICAL_AFTER_MS = 12 * 60 * 60 * 1000;
const REPORT_POLL_MS = 15 * 60 * 1000;

function snapshotHealth(generatedAt, now = Date.now()) {
  const generated = Date.parse(generatedAt);
  if (!Number.isFinite(generated)) return {state: 'unknown', ageMs: null};
  const ageMs = Math.max(0, Number(now) - generated);
  if (ageMs >= CRITICAL_AFTER_MS) return {state: 'critical', ageMs};
  if (ageMs >= STALE_AFTER_MS) return {state: 'stale', ageMs};
  return {state: 'fresh', ageMs};
}

function snapshotAgeLabel(ageMs) {
  if (!Number.isFinite(ageMs)) return 'an unknown time ago';
  const minutes = Math.max(0, Math.floor(ageMs / 60000));
  if (minutes < 2) return 'just now';
  if (minutes < 60) return `${minutes} minutes ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? '' : 's'} ago`;
}

function snapshotStatusMarkup(data) {
  const health = snapshotHealth(data.generated_at);
  const updated = Number.isFinite(Date.parse(data.generated_at))
    ? new Date(data.generated_at).toLocaleString()
    : 'unknown';
  const label = health.state === 'fresh' ? 'Data current' : snapshotAgeLabel(health.ageMs);
  return `<span class="freshness-status ${health.state}"><span class="freshness-dot"></span><span>Updated ${esc(updated)} · ${esc(label)}</span></span>`;
}

function snapshotWarningMarkup(data) {
  const health = snapshotHealth(data.generated_at);
  if (health.state === 'fresh') return '';
  const title = health.state === 'critical' ? 'Data is out of date' : health.state === 'stale' ? 'Data refresh delayed' : 'Data freshness unavailable';
  const detail = health.state === 'unknown'
    ? 'The latest snapshot has no readable collection time.'
    : `The last successful collection was ${snapshotAgeLabel(health.ageMs)}.`;
  return `<div class="freshness-warning ${health.state}" role="status"><strong>${esc(title)}</strong><span>${esc(detail)} Treat recommendations as provisional until the next collection completes.</span></div>`;
}

function refreshSnapshotHealth() {
  if (!DATA) return;
  document.getElementById('updated').innerHTML = snapshotStatusMarkup(DATA);
  const slot = document.getElementById('freshness-warning-slot');
  if (slot) slot.innerHTML = snapshotWarningMarkup(DATA);
}

function fixtureLabel(player, gameweek) {
  const gw = (player.fixtures || []).find(x => x.gameweek === gameweek) || (player.fixtures || [])[0];
  if (!gw?.matches?.length) return '-';
  return gw.matches.map(m => `${m.opponent} (${m.venue})`).join(' + ');
}

function gwDifficulty(gw) {
  const values = (gw?.matches || []).map(m => Number(m.difficulty)).filter(n => n >= 1 && n <= 5);
  if (!values.length) return null;
  return Math.round(values.reduce((a,b) => a + b, 0) / values.length);
}

function fixtureCells(player) {
  const fixtures = player.fixtures || [];
  if (!fixtures.length) return '<div class="fixture blank">No fixtures</div>';
  return fixtures.map(gw => {
    if (!gw.matches?.length) return `<div class="fixture blank"><strong>GW${gw.gameweek}</strong><span>-</span></div>`;
    const text = gw.matches.map(m => `${esc(m.opponent)} ${m.venue}`).join(' + ');
    const difficulty = gwDifficulty(gw);
    const cls = difficulty ? `fdr-${difficulty}` : 'fdr-3';
    return `<div class="fixture ${cls}" title="FPL fixture difficulty ${difficulty ?? 3}/5"><strong>GW${gw.gameweek}</strong><span>${text}</span></div>`;
  }).join('');
}

function availabilityClass(p) {
  const chance = p.chance_next_round;
  if (chance == null || Number(chance) >= 100) return '';
  if (Number(chance) >= 75) return 'warn';
  return 'bad';
}

function availabilityBadge(p) {
  const chance = p.chance_next_round;
  if (chance == null) return '<span class="badge good">Available</span>';
  if (Number(chance) >= 75) return `<span class="badge warn">${esc(chance)}% fit</span>`;
  return `<span class="badge bad">${esc(chance)}% fit</span>`;
}

function scoreClass(score) {
  const value = Number(score || 0);
  if (value >= 70) return 'high';
  if (value >= 45) return 'mid';
  return 'low';
}

function intelligenceStrip(p) {
  const intel = p.intelligence || {};
  if (intel.roster_score == null) return '<div class="placeholder-score">Intelligence pending next collection</div>';
  return `<div class="score-strip">
    <span class="score ${scoreClass(intel.roster_score)}"><small>Roster</small><strong>${esc(intel.roster_score)}</strong></span>
    <span class="score ${scoreClass(intel.stash_score)}"><small>Stash</small><strong>${esc(intel.stash_score)}</strong></span>
    <span class="score ${scoreClass(intel.fixture_score)}"><small>Fixtures</small><strong>${esc(intel.fixture_score)}</strong></span>
  </div>`;
}

function playerCard(p, ownershipLabel) {
  return `<article class="player-card" data-player-id="${esc(p.player_id)}">
    <div class="player-main">
      <div class="position">${esc(p.position || '?')}</div>
      <div><div class="player-name">${esc(p.player)}</div><div class="meta">${esc(p.club || '-')} · ${esc(p.total_points ?? 0)} pts</div></div>
    </div>
    <div class="fixture-strip">${fixtureCells(p)}</div>
    <div class="intel">
      <div class="badges"><span class="badge purple">${esc(ownershipLabel)}</span>${availabilityBadge(p)}</div>
      ${intelligenceStrip(p)}
      ${p.news ? `<div class="news">${esc(p.news)}</div>` : '<div class="news">No current player news</div>'}
    </div>
  </article>`;
}

function fplKitUrl(p) {
  const code = Number(p.team_code || 0);
  if (!code) return '';
  const goalkeeper = p.position === 'GKP' ? '_1' : '';
  return `https://fantasy.premierleague.com/dist/img/shirts/standard/shirt_${code}${goalkeeper}-66.png`;
}

function recommendedKit(p, compact = false) {
  const url = fplKitUrl(p);
  const cls = compact ? 'recommended-kit compact' : 'recommended-kit';
  const fallback = `<span class="kit-fallback">${esc(p.club || '')}</span>`;
  if (!url) return `<span class="${cls}">${fallback}</span>`;
  return `<span class="${cls}">${fallback}<img src="${esc(url)}" alt="${esc(p.club || '')} kit" loading="lazy" onerror="this.remove()"></span>`;
}

function pitchPlayer(p) {
  const gw = DATA.lineup?.gameweek || DATA.planning_gameweeks?.[0] || 1;
  const phase = DATA.outcome_diagnostics?.current?.phase;
  const points = ['LIVE','FINAL'].includes(phase) && p.event_points != null ? `${esc(p.event_points)} GW pts · ` : '';
  return `<button class="pitch-player recommended-player official-player ${availabilityClass(p)}" data-player-id="${esc(p.player_id)}" title="Open ${esc(p.player)} intelligence">
    ${recommendedKit(p)}
    <span class="recommended-card-plate official-card-plate">
      <span class="player-label">${esc(p.player)}</span>
      <span class="next-fixture">${esc(fixtureLabel(p, gw))}</span>
      <span class="start-score official-pick-status">${points}Official starter</span>
    </span>
  </button>`;
}

function officialBenchCard(p, index, gameweek) {
  const phase = DATA.outcome_diagnostics?.current?.phase;
  const points = ['LIVE','FINAL'].includes(phase) && p.event_points != null ? ` · ${esc(p.event_points)} GW pts` : '';
  return `<button class="bench-card recommended-bench-card official-bench-card" data-player-id="${esc(p.player_id)}" title="Open ${esc(p.player)} intelligence">
    ${recommendedKit(p, true)}
    <strong>Bench ${esc(index)} · ${esc(p.player)}</strong>
    <small>${esc(p.position)} · ${esc(fixtureLabel(p, gameweek))}${points} · Official pick</small>
  </button>`;
}

function renderPitch() {
  const lineup = DATA.lineup || {};
  if (!lineup.is_exact || !(lineup.starters || []).length) {
    return `<div class="lineup-warning"><strong>Exact lineup not available from the public Draft endpoint yet.</strong><span>The toolkit will not invent a starting XI. Your owned squad is shown below until the official picks payload becomes readable.</span></div>${groupPlayers(DATA.my_squad || [], 'YOUR SQUAD')}`;
  }
  const starters = lineup.starters || [];
  const bench = lineup.bench || [];
  const pos = name => starters.filter(p => p.position === name);
  const row = (cls, players) => `<div class="line ${cls}" style="grid-template-columns:repeat(${Math.max(players.length, 1)},minmax(0,1fr))">${players.map(pitchPlayer).join('')}</div>`;
  const formation = `${pos('DEF').length}-${pos('MID').length}-${pos('FWD').length}`;
  const outcome = DATA.outcome_diagnostics?.current;
  const phase = outcome?.phase;
  const total = outcome?.actual?.official_points;
  const scoreLabel = ['LIVE','FINAL'].includes(phase) && total != null ? `${phase === 'FINAL' ? 'Final score' : 'Live score'} ${esc(total)}` : `Gameweek ${esc(lineup.gameweek)}`;
  return `<section class="pitch-shell recommended-xi-shell official-lineup-shell">
    <div class="pitch-head"><div class="pitch-head-inner"><span>${esc(formation)} formation</span><span class="recommended-lineup-badge official-lineup-badge">Official picks</span><span>${scoreLabel}</span></div></div>
    <div class="pitch"><div class="halfway"></div>${row('gkp',pos('GKP'))}${row('def',pos('DEF'))}${row('mid',pos('MID'))}${row('fwd',pos('FWD'))}</div>
    <div class="bench"><h3>Official bench order</h3><div class="bench-row">${bench.map((p, index) => officialBenchCard(p, index + 1, lineup.gameweek)).join('')}</div></div>
  </section>`;
}

function controls() {
  if (VIEW === 'activity') return '';
  if (VIEW === 'squad') return `<div class="view-toggle"><button data-squad-mode="pitch" class="${SQUAD_MODE==='pitch'?'active':''}">Pitch View</button><button data-squad-mode="list" class="${SQUAD_MODE==='list'?'active':''}">List View</button></div>`;
  return `<input id="search" class="search" type="search" placeholder="Search player or club" value="${esc(QUERY)}">
    <select id="position"><option value="ALL">All positions</option>${['GKP','DEF','MID','FWD'].map(p => `<option value="${p}" ${POS===p?'selected':''}>${p}</option>`).join('')}</select>
    ${VIEW === 'available' ? `<select id="sort">
      <option value="roster" ${SORT==='roster'?'selected':''}>Sort: roster score</option>
      <option value="stash" ${SORT==='stash'?'selected':''}>Sort: stash score</option>
      <option value="fixtures" ${SORT==='fixtures'?'selected':''}>Sort: fixtures</option>
      <option value="points" ${SORT==='points'?'selected':''}>Sort: points</option>
      <option value="availability" ${SORT==='availability'?'selected':''}>Sort: fitness</option>
      <option value="name" ${SORT==='name'?'selected':''}>Sort: name</option>
    </select>` : ''}`;
}

function filtered(items) {
  const q = QUERY.trim().toLowerCase();
  return (items || []).filter(p => (POS === 'ALL' || p.position === POS) && (!q || `${p.player} ${p.club}`.toLowerCase().includes(q)));
}

function groupPlayers(items, label) {
  return ['GKP','DEF','MID','FWD'].map(pos => {
    const list = items.filter(p => p.position === pos);
    if (!list.length) return '';
    return `<section class="group"><div class="group-title"><h3>${pos}</h3><span class="count">${list.length} players</span></div><div class="player-list">${list.map(p => playerCard(p,label)).join('')}</div></section>`;
  }).join('');
}

function renderSquad() {
  return SQUAD_MODE === 'pitch' ? renderPitch() : groupPlayers(DATA.my_squad || [], 'YOUR SQUAD');
}

function renderAvailable() {
  let list = filtered(DATA.available_players || []);
  const score = (p,key) => Number(p.intelligence?.[key] || 0);
  if (SORT === 'roster') list.sort((a,b) => score(b,'roster_score') - score(a,'roster_score'));
  if (SORT === 'stash') list.sort((a,b) => score(b,'stash_score') - score(a,'stash_score'));
  if (SORT === 'fixtures') list.sort((a,b) => score(b,'fixture_score') - score(a,'fixture_score'));
  if (SORT === 'points') list.sort((a,b) => (b.total_points || 0) - (a.total_points || 0));
  if (SORT === 'availability') list.sort((a,b) => (b.chance_next_round ?? 100) - (a.chance_next_round ?? 100));
  if (SORT === 'name') list.sort((a,b) => String(a.player).localeCompare(String(b.player)));
  const shown = list.slice(0,100);
  return shown.length ? `<div class="group-title"><h3>Available players</h3><span class="count">Showing ${shown.length} of ${list.length}</span></div><div class="player-list">${shown.map(p => playerCard(p,'AVAILABLE')).join('')}</div>` : '<div class="empty">No available players match these filters.</div>';
}

function renderActivity() {
  const items = DATA.league_activity || [];
  if (!items.length) return '<div class="empty">No ownership changes have been detected since monitoring started. This panel will become the opponent-drop radar.</div>';
  return items.map(x => `<div class="activity-card"><strong>${esc(String(x.type || '').toUpperCase())}: ${esc(x.player)}</strong><div class="meta">${esc(x.from_owner_name || x.from_owner || 'Free pool')} → ${esc(x.to_owner_name || x.to_owner || 'Free pool')}</div></div>`).join('');
}

function renderPlanner() {
  const gws = DATA.planning_gameweeks || [1,2,3,4];
  const squad = DATA.my_squad || [];
  return `<div class="planner-grid">${gws.map(gw => `<section class="gw-panel"><div class="gw-head">GW${gw}</div><div class="gw-body">${squad.map(p => `<div class="gw-team"><span>${esc(p.player)}</span><strong>${esc(fixtureLabel(p,gw))}</strong></div>`).join('')}</div></section>`).join('')}</div>`;
}

function allPlayers() {
  const rows = [
    ...(DATA.my_squad || []),
    ...(DATA.available_players || []),
    ...(DATA.h2h_matchup?.opponent_squad || []),
  ];
  return [...new Map(rows.map(player => [String(player.player_id), player])).values()];
}
function openPlayer(id) {
  const p = allPlayers().find(x => String(x.player_id) === String(id));
  if (!p) return;
  const intel = p.intelligence || {};
  const drawer = document.getElementById('player-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  drawer.innerHTML = `<div class="drawer-head"><button id="drawer-close" aria-label="Close">×</button><div class="eyebrow">${esc(p.position)} · ${esc(p.club || '-')}</div><h2>${esc(p.player)}</h2><div>${esc(p.total_points ?? 0)} points</div></div>
    <div class="drawer-body"><div class="badges">${availabilityBadge(p)}</div>${intelligenceStrip(p)}<div class="drawer-fixtures">${(p.fixtures || []).map(g => `<div class="drawer-fixture fdr-${gwDifficulty(g) || 3}"><strong>GW${g.gameweek}</strong><div>${esc(fixtureLabel(p,g.gameweek))}</div><small>Difficulty ${esc(gwDifficulty(g) || 3)}/5</small></div>`).join('')}</div>
    <div class="drawer-section"><strong>Latest status</strong><div class="news">${esc(p.news || 'No current player news')}</div></div>
    <div class="drawer-section"><strong>How v0.1 scores this player</strong><div class="model-grid"><span>Position baseline <b>${esc(intel.baseline_score ?? '-')}</b></span><span>4-GW fixtures <b>${esc(intel.fixture_score ?? '-')}</b></span><span>Future fixtures <b>${esc(intel.future_fixture_score ?? '-')}</b></span><span>Availability <b>${esc(intel.availability_score ?? '-')}</b></span></div><div class="model-note">Roster = 45% position-relative historical points + 35% fixture outlook + 20% availability. Stash shifts weight toward future fixtures and only lightly penalizes current availability. This is an intentionally transparent first-pass model.</div></div></div>`;
  backdrop.hidden = false; drawer.classList.add('open'); drawer.setAttribute('aria-hidden','false');
  document.getElementById('drawer-close').addEventListener('click', closePlayer);
}
function closePlayer(){const d=document.getElementById('player-drawer');d.classList.remove('open');d.setAttribute('aria-hidden','true');document.getElementById('drawer-backdrop').hidden=true;}

function render() {
  const s = DATA.summary || {};
  const scoringGw = DATA.current_gameweek;
  const decisionGw = DATA.decision_gameweek ?? DATA.planning_gameweeks?.[0] ?? scoringGw;
  const gwLabel = scoringGw === 0
    ? `Planning GW${esc(decisionGw || 1)}`
    : Number(scoringGw) === Number(decisionGw)
      ? `Decisions · GW${esc(decisionGw)}`
      : `Live GW${esc(scoringGw)} · Plan GW${esc(decisionGw)}`;
  document.getElementById('hero').innerHTML = `<div class="hero-top"><div><div class="eyebrow">${esc(DATA.league_name || 'Draft league')}</div><h2>Your Gameweek decision centre</h2><p>Advice starts with GW${esc(decisionGw || 1)}, the first round your next lineup and waiver decisions can still affect.</p></div><div class="gw-pill">${gwLabel}</div></div>
    <div id="freshness-warning-slot">${snapshotWarningMarkup(DATA)}</div>
    <div class="stats"><div class="stat"><small>My squad</small><strong>${esc(s.my_squad_count)}</strong></div><div class="stat"><small>Available</small><strong>${esc(s.available_count)}</strong></div><div class="stat"><small>Changes</small><strong>${esc(s.ownership_changes)}</strong></div><button class="stat stat-button" data-view-link="injury"><small>Availability decisions</small><strong>${esc((DATA.injury_stash?.summary?.decision_count ?? s.injured_or_doubtful_count) + (DATA.injury_stash?.summary?.transfer_alerts || 0))}</strong><span>Open dashboard →</span></button></div>`;
  refreshSnapshotHealth();
  document.getElementById('controls').innerHTML = controls();
  document.querySelectorAll('.primary-link').forEach(btn => btn.classList.toggle('active', btn.dataset.view === VIEW));
  document.getElementById('content').innerHTML = VIEW === 'squad' ? renderSquad() : VIEW === 'available' ? renderAvailable() : VIEW === 'activity' ? renderActivity() : renderPlanner();
  bindControls(); bindPlayers();
}

function bindControls() {
  document.querySelectorAll('[data-squad-mode]').forEach(btn => btn.addEventListener('click', () => { SQUAD_MODE = btn.dataset.squadMode; render(); }));
  document.getElementById('search')?.addEventListener('input', e => { QUERY = e.target.value; render(); document.getElementById('search')?.focus(); });
  document.getElementById('position')?.addEventListener('change', e => { POS = e.target.value; render(); });
  document.getElementById('sort')?.addEventListener('change', e => { SORT = e.target.value; render(); });
  document.querySelectorAll('[data-view-link]').forEach(btn => btn.addEventListener('click', () => {
    VIEW = btn.dataset.viewLink;
    QUERY = '';
    POS = 'ALL';
    history.replaceState(null, '', `#${VIEW}`);
    render();
  }));
}
function bindPlayers(){document.querySelectorAll('[data-player-id]').forEach(el => el.addEventListener('click',()=>openPlayer(el.dataset.playerId)));}

document.querySelectorAll('.primary-link').forEach(btn => btn.addEventListener('click', () => { VIEW = btn.dataset.view; QUERY = ''; POS = 'ALL'; render(); }));
document.getElementById('drawer-backdrop').addEventListener('click', closePlayer);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closePlayer(); });

function loadReport() {
  return fetch(`data/latest.json?v=${Date.now()}`, {cache:'no-store'})
    .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then(data => { DATA = data; render(); })
    .catch(err => {
      if (!DATA) document.getElementById('content').innerHTML = `<div class="error"><strong>No live report yet.</strong><br>${esc(err.message)}</div>`;
    });
}

loadReport();
setInterval(refreshSnapshotHealth, 60 * 1000);
setInterval(loadReport, REPORT_POLL_MS);
