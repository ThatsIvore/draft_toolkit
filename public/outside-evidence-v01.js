// Outside Match Evidence v0.1.0. Display-only release; no collector dependency.
(() => {
  'use strict';

  const RELEASE = Object.freeze({
    enabled: true,
    gameweek: 13,
    waiversAt: '2026-11-30T18:30:00Z',
    lineupAt: '2026-12-01T18:30:00Z',
    rows: [
      { id: 4, club: 'ARS', name: 'Gabriel', competition: 'UEFA Champions League',
        opponent: 'Borussia Dortmund', date: '2026-11-24', role: 'Started',
        checkedAt: '2026-11-28T01:03:00Z', source: 'https://www.uefa.com/uefachampionsleague/match/2049627--arsenal-vs-dortmund/' },
      { id: 67, club: 'BOU', name: 'Rayan', competition: 'UEFA Europa League',
        opponent: 'Celta Vigo', date: '2026-11-26', role: 'Used substitute', enteredAt: 68,
        checkedAt: '2026-11-28T01:03:00Z', source: 'https://www.afcb.co.uk/news/2026/november/26/match-report-v-celta-vigo' },
      { id: 138, club: 'BHA', name: 'Kostoulas', competition: 'UEFA Conference League',
        opponent: 'Universitatea Craiova', date: '2026-11-26', role: 'Started',
        checkedAt: '2026-11-28T01:03:00Z', source: 'https://www.brightonandhovealbion.com/match-centre-lineups?gameId=2685870' },
    ],
  });

  const safeSource = (input) => {
    try {
      const u = new URL(input);
      return u.protocol === 'https:' && !u.username && !u.password && !u.port &&
        ['www.uefa.com', 'www.afcb.co.uk', 'www.brightonandhovealbion.com'].includes(u.hostname) ? u.href : null;
    } catch {
      return null;
    }
  };

  function render(player, gameweek, now = Date.now()) {
    const waiversAt = Date.parse(RELEASE.waiversAt);
    const lineupAt = Date.parse(RELEASE.lineupAt);
    if (!RELEASE.enabled || gameweek !== RELEASE.gameweek || !Number.isFinite(now) ||
        !Number.isFinite(waiversAt) || !Number.isFinite(lineupAt) ||
        waiversAt >= lineupAt || now >= lineupAt) return '';

    const hits = RELEASE.rows.filter(row => Number(player?.player_id) === row.id &&
      player?.club === row.club && player?.player === row.name);
    if (hits.length !== 1) return '';
    const row = hits[0];
    const source = safeSource(row.source);
    const checkedAt = Date.parse(row.checkedAt);
    const playedOn = Date.parse(row.date);
    if (!source || !Number.isFinite(playedOn) || !Number.isFinite(checkedAt) ||
        playedOn > checkedAt || checkedAt > now ||
        !['Started', 'Used substitute', 'Unused substitute'].includes(row.role)) return '';

    const scope = checkedAt >= waiversAt || now >= waiversAt ? 'Lineup context only; waivers have closed.' : 'Pre-deadline context.';
    const entry = Number.isInteger(row.enteredAt) && row.role === 'Used substitute'
      ? ` at ${esc(row.enteredAt)}′` : '';
    return `<section class="drawer-section" aria-label="Outside match evidence"><strong>Outside match evidence · GW${esc(gameweek)}</strong>
      <div class="news">${esc(row.role)}${entry} · ${esc(row.competition)} · vs ${esc(row.opponent)} · ${esc(row.date)}</div>
      <div class="model-note"><a href="${esc(source)}" target="_blank" rel="noopener noreferrer">Official match source</a> · Checked ${esc(row.checkedAt)}<br>
      ${scope} This appearance does not predict a Premier League start or change scores.</div></section>`;
  }

  window.draftOutsideEvidence = Object.freeze({ render });
})();
