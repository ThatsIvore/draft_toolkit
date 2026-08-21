const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

let DATA = null;
let VIEW = 'squad';
let SQUAD_MODE = 'pitch';
let QUERY = '';
let POS = 'ALL';
let SORT = 'points';

function fixtureLabel(player, gameweek) {
  const gw = (player.fixtures || []).find(x => x.gameweek === gameweek) || (player.fixtures || [])[0];
  if (!gw?.matches?.length) return '-';
  return gw.matches.map(m => `${m.opponent} (${m.venue})`).join(' + ');
}

function fixtureCells(player) {
  const fixtures = player.fixtures || [];
  if (!fixtures.length) return '<div class="fixture blank">No fixtures</div>';
  return fixtures.map(gw => {
    if (!gw.matches?.length) return `<div class="fixture blank"><strong>GW${gw.gameweek}</strong><span>-</span></div>`;
    const text = gw.matches.map(m => `${esc(m.opponent)} ${m.venue}`).join(' + ');
    const cls = gw.matches.length === 1 && gw.matches[0].venue === 'H' ? 'home' : 'away';
    return `<div class="fixture ${cls}"><strong>GW${gw.gameweek}</strong><span>${text}</span></div>`;
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

function playerCard(p, ownershipLabel) {
  return `<article class="player-card" data-player-id="${esc(p.player_id)}">
    <div class="player-main">
      <div class="position">${esc(p.position || '?')}</div>
      <div><div class="player-name">${esc(p.player)}</div><div class="meta">${esc(p.club || '-')} · ${esc(p.total_points ?? 0)} pts</div></div>
    </div>
    <div class="fixture-strip">${fixtureCells(p)}</div>
    <div class="intel">
      <div class="badges"><span class="badge purple">${esc(ownershipLabel)}</span>${availabilityBadge(p)}</div>
      ${p.news ? `<div class="news">${esc(p.news)}</div>` : '<div class="news">No current player news</div>'}
      <div class="placeholder-score">Roster / stash scoring: next phase</div>
    </div>
  </article>`;
}

function pitchPlayer(p) {
  const gw = DATA.lineup?.gameweek || DATA.planning_gameweeks?.[0] || 1;
  return `<button class="pitch-player ${availabilityClass(p)}" data-player-id="${esc(p.player_id)}" title="Open ${esc(p.player)} intelligence">
    <span class="shirt"><span>${esc(p.club || '')}</span></span><span class="intel-dot">i</span>
    <span class="player-label">${esc(p.player)}</span>
    <span class="next-fixture">${esc(fixtureLabel(p, gw))}</span>
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
  const row = (cls, players) => `<div class="line ${cls}">${players.map(pitchPlayer).join('')}</div>`;
  return `<section class="pitch-shell">
    <div class="pitch-head"><div class="pitch-head-inner"><span>Gameweek ${esc(lineup.gameweek)} lineup</span><span class="verified-lineup">Official picks</span></div></div>
    <div class="pitch"><div class="halfway"></div>${row('gkp',pos('GKP'))}${row('def',pos('DEF'))}${row('mid',pos('MID'))}${row('fwd',pos('FWD'))}</div>
    <div class="bench"><h3>Bench</h3><div class="bench-row">${bench.map(p => `<button class="bench-card" data-player-id="${esc(p.player_id)}"><span class="bench-shirt">${esc(p.club || '')}</span><strong>${esc(p.player)}</strong><small>${esc(p.position)} · ${esc(fixtureLabel(p, lineup.gameweek))}</small></button>`).join('')}</div></div>
  </section>`;
}

function controls() {
  if (VIEW === 'activity') return '';
  if (VIEW === 'squad') return `<div class="view-toggle"><button data-squad-mode="pitch" class="${SQUAD_MODE==='pitch'?'active':''}">Pitch View</button><button data-squad-mode="list" class="${SQUAD_MODE==='list'?'active':''}">List View</button></div>`;
  return `<input id="search" class="search" type="search" placeholder="Search player or club" value="${esc(QUERY)}">
    <select id="position"><option value="ALL">All positions</option>${['GKP','DEF','MID','FWD'].map(p => `<option value="${p}" ${POS===p?'selected':''}>${p}</option>`).join('')}</select>
    ${VIEW === 'available' ? `<select id="sort"><option value="points" ${SORT==='points'?'selected':''}>Sort: points</option><option value="availability" ${SORT==='availability'?'selected':''}>Sort: fitness</option><option value="name" ${SORT==='name'?'selected':''}>Sort: name</option></select>` : ''}`;
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

function allPlayers() { return [...(DATA.my_squad || []), ...(DATA.available_players || [])]; }
function openPlayer(id) {
  const p = allPlayers().find(x => String(x.player_id) === String(id));
  if (!p) return;
  const drawer = document.getElementById('player-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  drawer.innerHTML = `<div class="drawer-head"><button id="drawer-close" aria-label="Close">×</button><div class="eyebrow">${esc(p.position)} · ${esc(p.club || '-')}</div><h2>${esc(p.player)}</h2><div>${esc(p.total_points ?? 0)} points</div></div>
    <div class="drawer-body"><div class="badges">${availabilityBadge(p)}</div><div class="drawer-fixtures">${(p.fixtures || []).map(g => `<div class="drawer-fixture"><strong>GW${g.gameweek}</strong><div>${esc(fixtureLabel(p,g.gameweek))}</div></div>`).join('')}</div>
    <div class="drawer-section"><strong>Latest status</strong><div class="news">${esc(p.news || 'No current player news')}</div></div>
    <div class="drawer-section"><strong>Decision intelligence</strong><div class="placeholder-score">Expected starts, roster value, stash value and action recommendation will appear here in the next phase.</div></div></div>`;
  backdrop.hidden = false; drawer.classList.add('open'); drawer.setAttribute('aria-hidden','false');
  document.getElementById('drawer-close').addEventListener('click', closePlayer);
}
function closePlayer(){const d=document.getElementById('player-drawer');d.classList.remove('open');d.setAttribute('aria-hidden','true');document.getElementById('drawer-backdrop').hidden=true;}

function render() {
  const s = DATA.summary || {};
  document.getElementById('hero').innerHTML = `<div class="hero-top"><div><div class="eyebrow">${esc(DATA.league_name || 'Draft league')}</div><h2>Your Gameweek decision centre</h2><p>Familiar Draft views with squad, free-agent and future-Gameweek intelligence layered on top.</p></div><div class="gw-pill">${DATA.current_gameweek === 0 ? 'Pre-GW1' : `GW${esc(DATA.current_gameweek)}`}</div></div>
    <div class="stats"><div class="stat"><small>My squad</small><strong>${esc(s.my_squad_count)}</strong></div><div class="stat"><small>Available</small><strong>${esc(s.available_count)}</strong></div><div class="stat"><small>Changes</small><strong>${esc(s.ownership_changes)}</strong></div><div class="stat"><small>Injury watch</small><strong>${esc(s.injured_or_doubtful_count)}</strong></div></div>`;
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
}
function bindPlayers(){document.querySelectorAll('[data-player-id]').forEach(el => el.addEventListener('click',()=>openPlayer(el.dataset.playerId)));}

document.querySelectorAll('.primary-link').forEach(btn => btn.addEventListener('click', () => { VIEW = btn.dataset.view; QUERY = ''; POS = 'ALL'; render(); }));
document.getElementById('drawer-backdrop').addEventListener('click', closePlayer);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closePlayer(); });

fetch('data/latest.json', {cache:'no-store'})
  .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
  .then(data => { DATA = data; document.getElementById('updated').textContent = `Updated ${new Date(data.generated_at).toLocaleString()} · League ${data.league_id}`; render(); })
  .catch(err => { document.getElementById('content').innerHTML = `<div class="error"><strong>No live report yet.</strong><br>${esc(err.message)}</div>`; });
