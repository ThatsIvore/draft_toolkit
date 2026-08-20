const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

let DATA = null;
let VIEW = 'squad';
let QUERY = '';
let POS = 'ALL';
let SORT = 'points';

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

function availabilityBadge(p) {
  const chance = p.chance_next_round;
  if (chance == null) return '<span class="badge good">Available</span>';
  if (Number(chance) >= 75) return `<span class="badge warn">${esc(chance)}% fit</span>`;
  return `<span class="badge bad">${esc(chance)}% fit</span>`;
}

function playerCard(p, ownershipLabel) {
  return `<article class="player-card">
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

function controls() {
  if (VIEW === 'activity') return '';
  return `<input id="search" class="search" type="search" placeholder="Search player or club" value="${esc(QUERY)}">
    <select id="position"><option value="ALL">All positions</option>${['GKP','DEF','MID','FWD'].map(p => `<option ${POS===p?'selected':''}>${p}</option>`).join('')}</select>
    ${VIEW === 'available' ? `<select id="sort"><option value="points" ${SORT==='points'?'selected':''}>Sort: points</option><option value="availability" ${SORT==='availability'?'selected':''}>Sort: fitness</option><option value="name" ${SORT==='name'?'selected':''}>Sort: name</option></select>` : ''}`;
}

function filtered(items) {
  const q = QUERY.trim().toLowerCase();
  return (items || []).filter(p => (POS === 'ALL' || p.position === POS) && (!q || `${p.player} ${p.club}`.toLowerCase().includes(q)));
}

function groupPlayers(items, label) {
  const positions = ['GKP','DEF','MID','FWD'];
  return positions.map(pos => {
    const list = items.filter(p => p.position === pos);
    if (!list.length) return '';
    return `<section class="group"><div class="group-title"><h3>${pos}</h3><span class="count">${list.length} players</span></div><div class="player-list">${list.map(p => playerCard(p,label)).join('')}</div></section>`;
  }).join('');
}

function renderSquad() {
  const list = filtered(DATA.my_squad || []);
  return list.length ? groupPlayers(list, 'YOUR SQUAD') : '<div class="empty">No squad players match these filters.</div>';
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
  return `<div class="planner-grid">${gws.map(gw => {
    const rows = squad.map(p => {
      const f = (p.fixtures || []).find(x => x.gameweek === gw);
      const label = f?.matches?.length ? f.matches.map(m => `${m.opponent} (${m.venue})`).join(' + ') : '-';
      return `<div class="gw-team"><span>${esc(p.player)}</span><strong>${esc(label)}</strong></div>`;
    }).join('');
    return `<section class="gw-panel"><div class="gw-head">GW${gw}</div><div class="gw-body">${rows}</div></section>`;
  }).join('')}</div>`;
}

function render() {
  const s = DATA.summary || {};
  document.getElementById('hero').innerHTML = `<div class="hero-top"><div><div class="eyebrow">${esc(DATA.league_name || 'Draft league')}</div><h2>Your Gameweek decision centre</h2><p>Squad, free agents, injuries and the next ${esc(DATA.planning_horizon || 4)} Gameweeks in one view.</p></div><div class="gw-pill">${DATA.current_gameweek === 0 ? 'Pre-GW1' : `GW${esc(DATA.current_gameweek)}`}</div></div>
    <div class="stats"><div class="stat"><small>My squad</small><strong>${esc(s.my_squad_count)}</strong></div><div class="stat"><small>Available</small><strong>${esc(s.available_count)}</strong></div><div class="stat"><small>Changes</small><strong>${esc(s.ownership_changes)}</strong></div><div class="stat"><small>Injury watch</small><strong>${esc(s.injured_or_doubtful_count)}</strong></div></div>`;
  document.getElementById('controls').innerHTML = controls();
  document.querySelectorAll('.tab').forEach(btn => btn.classList.toggle('active', btn.dataset.view === VIEW));
  const content = document.getElementById('content');
  content.innerHTML = VIEW === 'squad' ? renderSquad() : VIEW === 'available' ? renderAvailable() : VIEW === 'activity' ? renderActivity() : renderPlanner();
  bindControls();
}

function bindControls() {
  document.getElementById('search')?.addEventListener('input', e => { QUERY = e.target.value; render(); document.getElementById('search')?.focus(); });
  document.getElementById('position')?.addEventListener('change', e => { POS = e.target.value; render(); });
  document.getElementById('sort')?.addEventListener('change', e => { SORT = e.target.value; render(); });
}

document.querySelectorAll('.tab').forEach(btn => btn.addEventListener('click', () => { VIEW = btn.dataset.view; QUERY = ''; POS = 'ALL'; render(); }));

fetch('data/latest.json', {cache:'no-store'})
  .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
  .then(data => {
    DATA = data;
    document.getElementById('updated').textContent = `Updated ${new Date(data.generated_at).toLocaleString()} · League ${data.league_id}`;
    render();
  })
  .catch(err => { document.getElementById('content').innerHTML = `<div class="error"><strong>No live report yet.</strong><br>${esc(err.message)}</div>`; });
