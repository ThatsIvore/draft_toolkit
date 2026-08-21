function changeFeed() {
  return DATA?.change_feed || {items: [], summary: {}, baseline: true};
}

function changePriorityLabel(priority) {
  if (priority === 'critical') return 'ACTION';
  if (priority === 'important') return 'IMPORTANT';
  if (priority === 'watch') return 'WATCH';
  return 'INFO';
}

function changePriorityRank(priority) {
  return {critical: 4, important: 3, watch: 2, info: 1}[priority] || 0;
}

function changeTimeLabel(raw) {
  if (!raw) return 'previous collection';
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return 'previous collection';
  return date.toLocaleString([], {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'});
}

function groupedChangeItems(items) {
  const playerGroups = new Map();
  const standalone = [];
  (items || []).forEach((item, index) => {
    if (item.player_id == null) {
      standalone.push({...item, _order: index});
      return;
    }
    const key = String(item.player_id);
    if (!playerGroups.has(key)) playerGroups.set(key, []);
    playerGroups.get(key).push({...item, _order: index});
  });

  const grouped = [...playerGroups.values()].map(events => {
    events.sort((a, b) => changePriorityRank(b.priority) - changePriorityRank(a.priority) || a._order - b._order);
    if (events.length === 1) return events[0];
    const primary = events[0];
    return {
      ...primary,
      kind: 'player_summary',
      title: `${primary.player || 'Player'}: ${events.length} material changes`,
      detail: '',
      badge: events.some(event => event.kind === 'availability') ? 'STATUS UPDATE' : 'MULTI CHANGE',
      grouped_events: events,
      _order: Math.min(...events.map(event => event._order)),
    };
  });

  return [...grouped, ...standalone].sort((a, b) =>
    changePriorityRank(b.priority) - changePriorityRank(a.priority) || (a._order || 0) - (b._order || 0)
  );
}

function groupedChangeSummary(items) {
  const summary = {critical: 0, important: 0, watch: 0, info: 0};
  groupedChangeItems(items).forEach(item => {
    const priority = item.priority || 'info';
    summary[priority] = (summary[priority] || 0) + 1;
  });
  return summary;
}

function changeItemCard(item) {
  const clickable = item.player_id != null ? ` data-player-id="${esc(item.player_id)}"` : '';
  const tag = item.player_id != null ? 'button' : 'article';
  const grouped = item.grouped_events || [];
  const body = grouped.length
    ? `<div class="change-detail-list">${grouped.map(event => `<div class="change-detail-row"><span>${esc(event.badge || event.kind || 'CHANGE')}</span><p><strong>${esc(event.title || 'Decision update')}</strong>${event.detail ? `<small>${esc(event.detail)}</small>` : ''}</p></div>`).join('')}</div>`
    : `<p>${esc(item.detail || '')}</p>`;
  return `<${tag} class="change-card priority-${esc(item.priority || 'info')}"${clickable}>
    <div class="change-card-head">
      <span class="change-priority">${esc(changePriorityLabel(item.priority))}</span>
      <span class="change-kind">${esc(item.badge || item.kind || 'CHANGE')}</span>
    </div>
    <strong>${esc(item.title || 'Decision update')}</strong>
    ${body}
    ${item.player ? `<small>${esc(item.position || '')}${item.position ? ' · ' : ''}${esc(item.player)}${item.club ? ` · ${esc(item.club)}` : ''}</small>` : ''}
  </${tag}>`;
}

function renderWhatChanged() {
  const feed = changeFeed();
  const rawItems = feed.items || [];
  const items = groupedChangeItems(rawItems);
  const summary = groupedChangeSummary(rawItems);
  if (feed.baseline && !items.length) {
    return `<section class="changes-v09">
      <div class="changes-intro"><div><div class="eyebrow">What Changed? · v0.9.3</div><h3>Decision baseline captured</h3><p>The toolkit now persists decision state. The next collection will surface only material changes in lineup, availability, role evidence, waivers, planning and H2H context.</p></div></div>
    </section>`;
  }
  return `<section class="changes-v09">
    <div class="changes-intro">
      <div><div class="eyebrow">What Changed? · v0.9.3</div><h3>Since ${esc(changeTimeLabel(feed.since))}</h3><p>Correlated changes for the same player are grouped into one decision card. Small score movement and transient live-match data are deliberately suppressed.</p></div>
      <div class="changes-summary">
        <span><small>Action</small><strong>${esc(summary.critical || 0)}</strong></span>
        <span><small>Important</small><strong>${esc(summary.important || 0)}</strong></span>
        <span><small>Watch</small><strong>${esc(summary.watch || 0)}</strong></span>
      </div>
    </div>
    ${items.length ? `<div class="change-grid">${items.map(changeItemCard).join('')}</div>` : `<div class="changes-empty"><strong>No material decision changes.</strong><span>The latest collection did not move any threshold enough to warrant action.</span></div>`}
    <div class="changes-note">${esc(feed.note || '')}</div>
  </section>`;
}

function playerChangeBadge(playerId) {
  const events = (changeFeed().items || []).filter(item => String(item.player_id) === String(playerId));
  if (!events.length) return '';
  events.sort((a, b) => changePriorityRank(b.priority) - changePriorityRank(a.priority));
  const event = events[0];
  const badge = events.length > 1 ? `${event.badge || 'CHANGED'} +${events.length - 1}` : (event.badge || 'CHANGED');
  return `<span class="player-change-chip priority-${esc(event.priority || 'info')}" title="${esc(event.title || 'Recent change')}">${esc(badge)}</span>`;
}

const v09PlayerCard = playerCard;
playerCard = function(p, ownershipLabel) {
  const html = v09PlayerCard(p, ownershipLabel);
  const chip = playerChangeBadge(p.player_id);
  if (!chip) return html;
  return html.replace(/(<article class="player-card"[^>]*>)/, `$1${chip}`);
};

const v09RecommendedPitchPlayer = recommendedPitchPlayer;
recommendedPitchPlayer = function(p) {
  const html = v09RecommendedPitchPlayer(p);
  const chip = playerChangeBadge(p.player_id);
  if (!chip) return html;
  return html.replace(/(<button class="pitch-player recommended-player[^>]*>)/, `$1${chip}`);
};

const v09RecommendedBenchCard = recommendedBenchCard;
recommendedBenchCard = function(p, label) {
  const html = v09RecommendedBenchCard(p, label);
  const chip = playerChangeBadge(p.player_id);
  if (!chip) return html;
  return html.replace(/(<button class="bench-card recommended-bench-card"[^>]*>)/, `$1${chip}`);
};

const v09Controls = controls;
controls = function() {
  if (VIEW === 'changes') return '';
  return v09Controls();
};

const v09RenderPlanner = renderPlanner;
renderPlanner = function() {
  if (VIEW === 'changes') return renderWhatChanged();
  return v09RenderPlanner();
};

const v09Render = render;
render = function() {
  v09Render();
  if (!DATA) return;
  const count = groupedChangeItems(changeFeed().items || []).length;
  const button = document.querySelector('[data-view="changes"]');
  if (button) button.innerHTML = `What Changed?${count ? `<span class="nav-change-count">${esc(count)}</span>` : ''}`;
  const heroStats = document.querySelectorAll('#hero .stat');
  const heroChangeValue = heroStats[2]?.querySelector('strong');
  if (heroChangeValue) heroChangeValue.textContent = String(count);
};
