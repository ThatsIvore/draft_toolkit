const CHANGE_SEEN_STORAGE_KEY = 'draft-toolkit-seen-decision-updates-v1';

function changeFeed() {
  return DATA?.change_feed || {items: [], archive: [], summary: {}, baseline: true};
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
  if (!raw) return 'cycle start';
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return 'cycle start';
  return date.toLocaleString([], {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'});
}

function changeItemKey(item) {
  return String(item.event_id || `${item.kind || 'change'}:${item.player_id ?? 'general'}:${item.title || ''}`);
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
      title: `${primary.player || 'Player'}: ${events.length} decision updates`,
      detail: '',
      badge: events.some(event => event.kind === 'availability') ? 'STATUS UPDATE' : 'MULTI UPDATE',
      grouped_events: events,
      _order: Math.min(...events.map(event => event._order)),
    };
  });

  return [...grouped, ...standalone].sort((a, b) =>
    changePriorityRank(b.priority) - changePriorityRank(a.priority) || String(b.last_seen || '').localeCompare(String(a.last_seen || '')) || (a._order || 0) - (b._order || 0)
  );
}

function changeItemCard(item) {
  const clickable = item.player_id != null ? ` data-player-id="${esc(item.player_id)}"` : '';
  const tag = item.player_id != null ? 'button' : 'article';
  const grouped = item.grouped_events || [];
  const body = grouped.length
    ? `<div class="change-detail-list">${grouped.map(event => `<div class="change-detail-row"><span>${esc(event.badge || event.kind || 'UPDATE')}</span><p><strong>${esc(event.title || 'Decision update')}</strong>${event.detail ? `<small>${esc(event.detail)}</small>` : ''}</p></div>`).join('')}</div>`
    : `<p>${esc(item.detail || '')}</p>`;
  const resolved = item.status === 'resolved';
  const timing = resolved && item.resolved_at
    ? `First seen ${changeTimeLabel(item.first_seen)} · Resolved ${changeTimeLabel(item.resolved_at)}`
    : `First seen ${changeTimeLabel(item.first_seen)}`;
  return `<${tag} class="change-card priority-${esc(item.priority || 'info')} status-${resolved ? 'resolved' : 'active'}"${clickable}>
    <div class="change-card-head">
      <span class="change-priority">${esc(changePriorityLabel(item.priority))}</span>
      <span class="change-kind">${esc(item.badge || item.kind || 'UPDATE')}</span>
    </div>
    <strong>${esc(item.title || 'Decision update')}</strong>
    ${body}
    ${item.player ? `<small>${esc(item.position || '')}${item.position ? ' · ' : ''}${esc(item.player)}${item.club ? ` · ${esc(item.club)}` : ''}</small>` : ''}
    <small class="change-time">${esc(timing)}</small>
  </${tag}>`;
}

function renderChangeSection(title, description, items, className) {
  const grouped = groupedChangeItems(items);
  if (!grouped.length) return '';
  return `<section class="change-section ${esc(className)}">
    <div class="change-section-head"><div><h3>${esc(title)}</h3><p>${esc(description)}</p></div><strong>${esc(grouped.length)}</strong></div>
    <div class="change-grid">${grouped.map(changeItemCard).join('')}</div>
  </section>`;
}

function renderChangeArchive(archive) {
  if (!(archive || []).length) return '';
  return `<section class="changes-archive"><h3>Earlier decision cycles</h3>${[...archive].reverse().map(cycle => {
    const items = groupedChangeItems(cycle.items || []);
    return `<details><summary><span>GW${esc(cycle.gameweek || '?')} archive</span><small>${esc(items.length)} updates · ended ${esc(changeTimeLabel(cycle.ended_at))}</small></summary><div class="change-grid archive-grid">${items.map(changeItemCard).join('')}</div></details>`;
  }).join('')}</section>`;
}

function seenDecisionUpdateIds() {
  try {
    const parsed = JSON.parse(localStorage.getItem(CHANGE_SEEN_STORAGE_KEY) || '[]');
    return new Set(Array.isArray(parsed) ? parsed.map(String) : []);
  } catch (_) {
    return new Set();
  }
}

function actionableDecisionUpdates() {
  return (changeFeed().items || []).filter(item =>
    (item.status || 'active') === 'active' && ['critical', 'important'].includes(item.priority)
  );
}

function unseenDecisionUpdateCount() {
  const seen = seenDecisionUpdateIds();
  return actionableDecisionUpdates().filter(item => !seen.has(changeItemKey(item))).length;
}

function markDecisionUpdatesSeen() {
  if (VIEW !== 'changes') return;
  const seen = seenDecisionUpdateIds();
  actionableDecisionUpdates().forEach(item => seen.add(changeItemKey(item)));
  try {
    localStorage.setItem(CHANGE_SEEN_STORAGE_KEY, JSON.stringify([...seen].slice(-200)));
  } catch (_) {}
}

function renderWhatChanged() {
  const feed = changeFeed();
  const rawItems = feed.items || [];
  const activeItems = rawItems.filter(item => (item.status || 'active') === 'active');
  const actionItems = activeItems.filter(item => ['critical', 'important'].includes(item.priority));
  const watchItems = activeItems.filter(item => item.priority === 'watch');
  const recentItems = rawItems.filter(item => item.status === 'resolved' || ((item.status || 'active') === 'active' && item.priority === 'info'));
  const actionCount = groupedChangeItems(actionItems).length;
  const watchCount = groupedChangeItems(watchItems).length;
  const recentCount = groupedChangeItems(recentItems).length;
  const gameweek = feed.cycle_gameweek ?? DATA?.decision_gameweek ?? DATA?.current_gameweek ?? '?';

  return `<section class="changes-v09">
    <div class="changes-intro">
      <div><div class="eyebrow">Decision Updates · v1.0</div><h3>GW${esc(gameweek)} decision cycle</h3><p>What has changed that could affect your next lineup or waiver decisions? Material updates remain here for the whole cycle instead of disappearing after the next collection.</p><small class="cycle-start">Tracking since ${esc(changeTimeLabel(feed.cycle_started_at || feed.since))}</small></div>
      <div class="changes-summary">
        <span><small>Action needed</small><strong>${esc(actionCount)}</strong></span>
        <span><small>Monitor</small><strong>${esc(watchCount)}</strong></span>
        <span><small>Recent</small><strong>${esc(recentCount)}</strong></span>
      </div>
    </div>
    ${rawItems.length ? `
      ${renderChangeSection('Action needed', `Important changes that may alter a GW${gameweek} decision.`, actionItems, 'section-action')}
      ${renderChangeSection('Worth monitoring', 'Signals to keep in view before the decision deadline.', watchItems, 'section-watch')}
      ${renderChangeSection('Resolved and recent', 'Closed opportunities, superseded signals and useful cycle context.', recentItems, 'section-recent')}
    ` : `<div class="changes-empty"><strong>No material GW${esc(gameweek)} decision updates yet.</strong><span>When something actionable changes, it will remain here through the decision cycle.</span></div>`}
    ${renderChangeArchive(feed.archive || [])}
    <div class="changes-note">${esc(feed.note || '')}</div>
  </section>`;
}

function playerChangeBadge(playerId) {
  const events = (changeFeed().items || []).filter(item =>
    String(item.player_id) === String(playerId) && (item.status || 'active') === 'active' && item.priority !== 'info'
  );
  if (!events.length) return '';
  events.sort((a, b) => changePriorityRank(b.priority) - changePriorityRank(a.priority));
  const event = events[0];
  const badge = events.length > 1 ? `${event.badge || 'UPDATED'} +${events.length - 1}` : (event.badge || 'UPDATED');
  return `<span class="player-change-chip priority-${esc(event.priority || 'info')}" title="${esc(event.title || 'Decision update')}">${esc(badge)}</span>`;
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
  const activeCount = groupedChangeItems((changeFeed().items || []).filter(item =>
    (item.status || 'active') === 'active' && item.priority !== 'info'
  )).length;
  const button = document.querySelector('[data-view="changes"]');
  const unread = unseenDecisionUpdateCount();
  if (button) button.innerHTML = `Decision Updates${unread ? `<span class="nav-change-count">${esc(unread)}</span>` : ''}`;
  const heroStats = document.querySelectorAll('#hero .stat');
  const heroChangeLabel = heroStats[2]?.querySelector('small');
  const heroChangeValue = heroStats[2]?.querySelector('strong');
  if (heroChangeLabel) heroChangeLabel.textContent = 'Decision updates';
  if (heroChangeValue) heroChangeValue.textContent = String(activeCount);
  if (VIEW === 'changes') {
    markDecisionUpdatesSeen();
    if (button) button.textContent = 'Decision Updates';
  }
};
