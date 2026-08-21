// Keep the search input in place while typing so the browser preserves the
// user's caret/selection. The original input handler performs a full render,
// which replaces the input node and resets the caret to the start.
document.addEventListener('input', event => {
  const input = event.target;
  if (!(input instanceof HTMLInputElement) || input.id !== 'search') return;

  // Prevent the legacy bubbling handler in app.js from replacing #controls.
  event.stopImmediatePropagation();
  QUERY = input.value;

  const content = document.getElementById('content');
  if (!content) return;

  if (VIEW === 'available') {
    content.innerHTML = renderAvailable();
  } else if (VIEW === 'planner') {
    content.innerHTML = renderPlanner();
  } else {
    return;
  }

  // Results were replaced, so restore the click handlers on player rows.
  bindPlayers();
}, true);
