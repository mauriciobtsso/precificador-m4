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
  await chrome.tabs.sendMessage(tab.id, {type: 'M4_FILL_NOW'}).catch(() => {});
  status.textContent = 'Preenchimento solicitado. Revise os campos da página.';
});
