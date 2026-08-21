function changeFeed() {
  return DATA?.change_feed || {items: [], summary: {}, baseline: true};
}

function changePriorityLabel(priority) {
  if (priority === 'critical') return 'ACTION';
  if (priority === 'important') return 'IMPORTANT';
  if (priority === 'watch') return 'WATCH';
  return 'INFO';
}

function changeTimeLabel(raw) {
  if (!raw) return 'previous collection';
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return 'previous collection';
  return date.toLocaleString([], {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'});
}

function changeItemCard(item) {
  const clickable = item.player_id != null ? ` data-player-id="${esc(item.player_id)}"` : '';
  const tag = item.player_id != null ? 'button' : 'article';
  return `<${tag} class="change-card priority-${esc(item.priority || 'info')}"${clickable}>
    <div class="change-card-head">
      <span class="change-priority">${esc(changePriorityLabel(item.priority))}</span>
      <span class="change-kind">${esc(item.badge || item.kind || 'CHANGE')}</span>
    </div>
    <strong>${esc(item.title || 'Decision update')}</strong>
    <p>${esc(item.detail || '')}</p>
    ${item.player ? `<small>${esc(item.position || '')}${item.position ? ' · ' : ''}${esc(item.player)}${item.club ? ` · ${esc(item.club)}` : ''}</small>` : ''}
  </${tag}>`;
}

function renderWhatChanged() {
  const feed = changeFeed();
  const items = feed.items || [];
  const summary = feed.summary || {};
  if (feed.baseline && !items.length) {
    return `<section class="changes-v09">
      <div class="changes-intro"><div><div class="eyebrow">What Changed? · v0.9</div><h3>Decision baseline captured</h3><p>The toolkit now persists decision state. The next collection will surface only material changes in lineup, availability, role evidence, waivers, planning and H2H context.</p></div></div>
    </section>`;
  }
  return `<section class="changes-v09">
    <div class="changes-intro">
      <div><div class="eyebrow">What Changed? · v0.9</div><h3>Since ${esc(changeTimeLabel(feed.since))}</h3><p>Material decision changes only. Small score movement is deliberately suppressed so this remains a useful action feed.</p></div>
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
  const event = events[0];
  return `<span class="player-change-chip priority-${esc(event.priority || 'info')}" title="${esc(event.title || 'Recent change')}">${esc(event.badge || 'CHANGED')}</span>`;
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