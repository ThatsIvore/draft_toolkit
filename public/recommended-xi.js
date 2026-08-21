function recommendedPitchPlayer(p) {
  const selection = p.selection || {};
  const gw = DATA.recommended_lineup?.gameweek || DATA.planning_gameweeks?.[0] || 1;
  const evidence = selection.role_evidence ? `${esc(selection.role_evidence)} evidence` : '';
  return `<button class="pitch-player recommended-player ${availabilityClass(p)}" data-player-id="${esc(p.player_id)}" title="Open ${esc(p.player)} intelligence${evidence ? ` · ${evidence}` : ''}">
    ${recommendedKit(p)}
    <span class="recommended-card-plate">
      <span class="player-label">${esc(p.player)}</span>
      <span class="next-fixture">${esc(fixtureLabel(p, gw))}</span>
      <span class="start-score" title="Toolkit Start Score; not projected FPL points">Start ${esc(selection.start_score ?? '-')}</span>
    </span>
  </button>`;
}

function recommendedBenchCard(p, label) {
  const selection = p.selection || {};
  const gw = DATA.recommended_lineup?.gameweek || DATA.planning_gameweeks?.[0] || 1;
  const evidence = selection.role_evidence ? ` · ${esc(selection.role_evidence)} evidence` : '';
  return `<button class="bench-card recommended-bench-card" data-player-id="${esc(p.player_id)}">
    ${recommendedKit(p, true)}
    <strong>${esc(label)} · ${esc(p.player)}</strong>
    <small>${esc(p.position)} · ${esc(fixtureLabel(p, gw))} · Start ${esc(selection.start_score ?? '-')}${evidence}</small>
  </button>`;
}

function closeCallBanner(call) {
  if (!call) return '';
  return `<div class="close-call-banner"><strong>Close selection call</strong><span>${esc(call.starter)} starts over ${esc(call.alternative)} by only ${esc(call.margin)} Start Score. Treat this as marginal, not decisive.</span></div>`;
}

function renderRecommendedPitch() {
  const rec = DATA.recommended_lineup || {};
  if (!rec.is_valid || !(rec.starters || []).length) {
    return `<div class="lineup-warning"><strong>Recommended XI unavailable.</strong><span>The toolkit could not construct a legal XI from the current squad data.</span></div>${groupPlayers(DATA.my_squad || [], 'YOUR SQUAD')}`;
  }
  const starters = rec.starters || [];
  const pos = name => starters.filter(p => p.position === name);
  const row = (cls, players) => `<div class="line ${cls}" style="grid-template-columns:repeat(${Math.max(players.length, 1)},minmax(0,1fr))">${players.map(recommendedPitchPlayer).join('')}</div>`;
  const reserve = rec.reserve_goalkeeper;
  const bench = rec.bench || [];
  const benchCards = [
    reserve ? recommendedBenchCard(reserve, 'Reserve GKP') : '',
    ...bench.map((player, index) => recommendedBenchCard(player, `Bench ${index + 1}`)),
  ].join('');
  const primaryCloseCall = (rec.close_calls || [])[0];
  return `<div class="recommendation-banner"><strong>Toolkit Recommended XI · GW${esc(rec.gameweek)}</strong><span>This is decision support only—not your submitted Draft lineup and not a projected-points model.</span></div>
    ${closeCallBanner(primaryCloseCall)}
    <section class="pitch-shell recommended-xi-shell">
      <div class="pitch-head"><div class="pitch-head-inner"><span>${esc(rec.formation)} formation</span><span class="recommended-lineup-badge">Recommended · v0.6.2</span><span>Avg Start Score ${esc(rec.average_start_score ?? '-')}</span></div></div>
      <div class="pitch"><div class="halfway"></div>${row('gkp',pos('GKP'))}${row('def',pos('DEF'))}${row('mid',pos('MID'))}${row('fwd',pos('FWD'))}</div>
      <div class="bench"><h3>Recommended bench order</h3><div class="bench-row">${benchCards}</div></div>
    </section>`;
}

const v06Controls = controls;
controls = function() {
  if (VIEW !== 'squad') return v06Controls();
  return `<div class="view-toggle lineup-view-toggle">
    <button data-squad-mode="pitch" class="${SQUAD_MODE==='pitch'?'active':''}">Official Lineup</button>
    <button data-squad-mode="recommended" class="${SQUAD_MODE==='recommended'?'active':''}">Recommended XI</button>
    <button data-squad-mode="list" class="${SQUAD_MODE==='list'?'active':''}">Squad List</button>
  </div>`;
};

const v06RenderSquad = renderSquad;
renderSquad = function() {
  if (SQUAD_MODE === 'recommended') return renderRecommendedPitch();
  return v06RenderSquad();
};
