(() => {
  const node = document.querySelector('[data-m4-client-payload]');
  if (!node) return;
  try {
    const payload = JSON.parse(node.textContent || node.dataset.m4ClientPayload || '{}');
    if (payload && payload.id) chrome.storage.local.set({m4ClienteSelecionado: payload, m4ClienteSelecionadoEm: Date.now()});
  } catch (error) { console.warn('[M4] payload inválido', error); }
  document.querySelectorAll('[data-m4-portal]').forEach((link) => {
    link.addEventListener('click', () => {
      try { chrome.storage.local.set({m4ClienteSelecionado: JSON.parse(node.textContent || '{}'), m4ClienteSelecionadoEm: Date.now()}); } catch (_) {}
    });
  });
})();
