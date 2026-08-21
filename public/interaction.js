function enhancePlayerCards(root = document) {
  root.querySelectorAll?.('.player-card[data-player-id]').forEach(card => {
    if (card.dataset.interactionEnhanced === 'true') return;
    card.dataset.interactionEnhanced = 'true';
    card.tabIndex = 0;
    card.setAttribute('role', 'button');
    const name = card.querySelector('.player-name')?.textContent?.trim() || 'player';
    card.setAttribute('title', `View ${name} details`);
    card.setAttribute('aria-label', `View ${name} details`);
    card.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        card.click();
      }
    });
  });
}

enhancePlayerCards();

new MutationObserver(mutations => {
  for (const mutation of mutations) {
    mutation.addedNodes.forEach(node => {
      if (node.nodeType === Node.ELEMENT_NODE) enhancePlayerCards(node);
    });
  }
}).observe(document.getElementById('content'), {childList: true, subtree: true});
