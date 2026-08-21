function plannerDifficultyClass(value) {
  const difficulty = Number(value);
  if (!Number.isFinite(difficulty)) return 'planner-blank';
  return `fdr-${Math.max(1, Math.min(5, Math.round(difficulty)))}`;
}

function plannerScore(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(1) : '-';
}

function plannerSignalClass(signal) {
  if (signal === 'STRONG RUN') return 'good';
  if (signal === 'WEAK WINDOW') return 'bad';
  return 'neutral';
}

function plannerWeekSummary(week, weakestGameweek) {
  const weak = Number(week.gameweek) === Number(weakestGameweek);
  return `<div class="planner-week-summary ${weak ? 'weakest' : ''}">
    <div><small>GW${esc(week.gameweek)}</small><strong>${plannerScore(week.average_schedule_score)}</strong></div>
    <span>${esc(week.formation || '-')} · ${esc(week.low_schedule_starters || 0)} weak-slot${Number(week.low_schedule_starters) === 1 ? '' : 's'}</span>
    ${weak ? '<b>Weakest upcoming GW</b>' : ''}
  </div>`;
}

function plannerFixtureCell(week) {
  return `<div class="planner-fixture-cell ${plannerDifficultyClass(week.difficulty)}" title="Schedule Score ${esc(plannerScore(week.schedule_score))}">
    <strong>${esc(week.fixture || 'Blank')}</strong>
    <small>Schedule ${esc(plannerScore(week.schedule_score))}</small>
  </div>`;
}

function plannerRosterRow(row) {
  return `<button class="planner-roster-row" data-player-id="${esc(row.player_id)}">
    <span class="planner-player"><b>${esc(row.player)}</b><small>${esc(row.position)} · ${esc(row.club || '-')}</small></span>
    <span class="planner-metric"><small>Roster</small><strong>${esc(plannerScore(row.roster_value))}</strong></span>
    <span class="planner-metric"><small>Next Start</small><strong>${esc(plannerScore(row.next_start_score))}</strong></span>
    ${(row.weeks || []).map(plannerFixtureCell).join('')}
    <span class="planner-metric planner-average"><small>4-GW</small><strong>${esc(plannerScore(row.average_schedule_score))}</strong></span>
    <span class="planner-signal ${plannerSignalClass(row.signal)}">${esc(row.signal || 'MIXED')}</span>
  </button>`;
}

function plannerTargetCard(target) {
  const kitPlayer = {team_code: target.team_code, club: target.add_club, position: target.position};
  return `<button class="streamer-card" data-player-id="${esc(target.add_player_id)}">
    <div class="streamer-head">${recommendedKit(kitPlayer, true)}<div><span class="streamer-label ${target.label === 'SCHEDULE UPGRADE' ? 'upgrade' : ''}">${esc(target.label)}</span><h4>${esc(target.add_player)}</h4><small>${esc(target.position)} · ${esc(target.add_club || '-')} · ${esc(target.role_evidence || 'LOW')} evidence</small></div></div>
    <div class="streamer-swap">Best schedule comparison: <strong>${esc(target.add_player)} for ${esc(target.drop_player)}</strong></div>
    <div class="streamer-deltas">
      <span><small>4-GW schedule</small><strong>+${esc(plannerScore(target.schedule_delta))}</strong></span>
      <span><small>Roster value</small><strong>${Number(target.roster_delta) >= 0 ? '+' : ''}${esc(plannerScore(target.roster_delta))}</strong></span>
      <span><small>Next Start</small><strong>${Number(target.next_start_delta) >= 0 ? '+' : ''}${esc(plannerScore(target.next_start_delta))}</strong></span>
    </div>
    <div class="streamer-run">${(target.weeks || []).map(week => `<span class="${plannerDifficultyClass(week.difficulty)}">GW${esc(week.gameweek)} ${esc(week.fixture)}</span>`).join('')}</div>
  </button>`;
}

const v07RenderPlanner = renderPlanner;
renderPlanner = function() {
  const planner = DATA.schedule_planner;
  if (!planner || !(planner.roster_rows || []).length) return v07RenderPlanner();
  const weeks = planner.weeks || [];
  const targets = planner.streamer_targets || [];
  return `<section class="planner-v07">
    <div class="planner-intro">
      <div><div class="eyebrow">Planner · v0.7</div><h3>Four-Gameweek squad outlook</h3><p>Schedule Score measures fixture-window usefulness. It is separate from next-GW Start Score and longer-term Roster Value.</p></div>
      <span class="planner-note">${esc(planner.note || '')}</span>
    </div>
    <div class="planner-week-strip">${weeks.map(week => plannerWeekSummary(week, planner.weakest_gameweek)).join('')}</div>
    <div class="planner-section-head"><div><h3>Squad schedule matrix</h3><p>Identify players whose fixture window becomes weak before it becomes an urgent waiver problem.</p></div></div>
    <div class="planner-table-scroll">
      <div class="planner-table-head"><span>Player</span><span>Roster</span><span>Next Start</span>${(planner.gameweeks || []).map(gw => `<span>GW${esc(gw)}</span>`).join('')}<span>4-GW</span><span>Window</span></div>
      <div class="planner-roster-table">${planner.roster_rows.map(plannerRosterRow).join('')}</div>
    </div>
    <div class="planner-section-head streamer-title"><div><h3>Fixture streamer targets</h3><p>Available same-position players whose four-Gameweek schedule improves your weakest comparable roster slot. This is schedule guidance, not an automatic drop instruction.</p></div></div>
    ${targets.length ? `<div class="streamer-grid">${targets.map(plannerTargetCard).join('')}</div>` : '<div class="empty">No available player currently clears the schedule-streamer threshold against your roster.</div>'}
  </section>`;
};
