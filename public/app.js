const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function fixtureText(item) {
  return (item.fixtures || []).map(g => {
    if (!g.matches?.length) return `GW${g.gameweek}: -`;
    return `GW${g.gameweek}: ` + g.matches.map(m => `${m.opponent}(${m.venue})`).join(' + ');
  }).join(' | ');
}

function rows(items, columns) {
  if (!items?.length) return '<p class="muted">No items in the latest snapshot.</p>';
  return `<table><thead><tr>${columns.map(c => `<th>${esc(c[0])}</th>`).join('')}</tr></thead><tbody>` +
    items.slice(0, 50).map(item => `<tr>${columns.map(c => `<td>${esc(c[1](item))}</td>`).join('')}</tr>`).join('') +
    '</tbody></table>';
}

fetch('data/latest.json', {cache: 'no-store'})
  .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
  .then(data => {
    document.getElementById('updated').textContent = `Updated ${new Date(data.generated_at).toLocaleString()} | League ${data.league_id}`;
    const s = data.summary || {};
    document.getElementById('content').innerHTML = `
      <div class="grid">
        <div class="card"><div class="muted">My squad</div><div class="value">${esc(s.my_squad_count)}</div></div>
        <div class="card"><div class="muted">Available</div><div class="value">${esc(s.available_count)}</div></div>
        <div class="card"><div class="muted">Changes</div><div class="value">${esc(s.ownership_changes)}</div></div>
        <div class="card"><div class="muted">Injury watch</div><div class="value">${esc(s.injured_or_doubtful_count)}</div></div>
      </div>
      <section><h2>League activity</h2>${rows(data.league_activity, [
        ['Action', x => x.type], ['Player', x => x.player], ['From', x => x.from_owner_name || x.from_owner || '-'], ['To', x => x.to_owner_name || x.to_owner || '-']
      ])}</section>
      <section><h2>My squad</h2>${rows(data.my_squad, [
        ['Player', x => x.player], ['Pos', x => x.position], ['Club', x => x.club], ['Availability', x => x.chance_next_round ?? '-'], ['Fixtures', x => fixtureText(x)], ['News', x => x.news || '-']
      ])}</section>
      <section><h2>Available players</h2>${rows(data.available_players, [
        ['Player', x => x.player], ['Pos', x => x.position], ['Club', x => x.club], ['Points', x => x.total_points ?? '-'], ['Fixtures', x => fixtureText(x)], ['News', x => x.news || '-']
      ])}</section>`;
  })
  .catch(err => {
    document.getElementById('content').innerHTML = `<div class="error"><strong>No live report yet.</strong><br>${esc(err.message)}. Run the collector once with a valid Draft entry ID.</div>`;
  });
