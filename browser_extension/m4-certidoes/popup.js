const status = document.getElementById('status');
const details = document.getElementById('details');
const button = document.getElementById('fill');
let cliente;
const mostrarCliente = ({m4ClienteSelecionado, m4ClienteSelecionadoEm}) => {
  if (!m4ClienteSelecionado || !m4ClienteSelecionadoEm || Date.now() - m4ClienteSelecionadoEm > 30 * 60 * 1000) {
    status.textContent = 'Nenhum cliente selecionado. Abra o cadastro no M4 primeiro.';
    status.className = 'warn';
    return;
  }
  cliente = m4ClienteSelecionado;
  status.textContent = 'Cliente pronto para preenchimento:';
  status.className = 'ok';
  details.innerHTML = `<strong>${cliente.nome || 'Sem nome'}</strong><br><span class="muted">CPF: ${cliente.cpf || 'não informado'}</span>`;
  button.disabled = false;
};
const carregarCliente = async () => {
  let salvo = await chrome.storage.local.get(['m4ClienteSelecionado', 'm4ClienteSelecionadoEm']);
  if (!salvo.m4ClienteSelecionado) {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (tab?.id) {
      try {
        const [resultado] = await chrome.scripting.executeScript({target: {tabId: tab.id}, func: () => {
          const node = document.querySelector('[data-m4-client-payload]');
          if (!node) return null;
          try { return JSON.parse(node.textContent || node.dataset.m4ClientPayload || '{}'); } catch (_) { return null; }
        }});
        if (resultado?.result?.id) {
          await chrome.storage.local.set({m4ClienteSelecionado: resultado.result, m4ClienteSelecionadoEm: Date.now()});
          salvo = await chrome.storage.local.get(['m4ClienteSelecionado', 'm4ClienteSelecionadoEm']);
        }
      } catch (_) {}
    }
  }
  mostrarCliente(salvo);
};
carregarCliente();
button.addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  if (!tab?.id) return;
  let response = {ok: false, filled: 0};
  try {
    // portal-fill.js também possui all_frames no manifest. A injeção explícita
    // aqui permite testar uma página que já estava aberta antes da extensão.
    await chrome.scripting.executeScript({target: {tabId: tab.id, allFrames: true}, files: ['portal-fill.js']});
    response = await chrome.tabs.sendMessage(tab.id, {type: 'M4_FILL_NOW'}).catch(() => response);
  } catch (error) {
    try {
      await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ['portal-fill.js']});
      response = await chrome.tabs.sendMessage(tab.id, {type: 'M4_FILL_NOW'}).catch(() => response);
    } catch (_) {
      status.textContent = 'Não foi possível acessar esta página. Recarregue o portal e tente novamente.';
      status.className = 'warn';
      return;
    }
  }
  status.textContent = response?.ok
    ? `Preenchimento solicitado: ${response.filled} campos neste quadro. Revise a página.`
    : 'Nenhum campo compatível foi encontrado nesta página.';
  status.className = response?.ok ? 'ok' : 'warn';
});
