(() => {
  const norm = (value) => (value || '').toString().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const selectors = {
    cpf: ['#cpf','[name="cpf"]','[name*="cpf" i]','[id*="cpf" i]','[name*="documento" i]'],
    nome: ['#nome','[name="nome"]','[name*="nome" i]','[name*="name" i]'],
    rg: ['#rg','[name="rg"]','[name*="rg" i]'],
    data_nascimento: ['#dataNascimento','[name*="nascimento" i]','[name*="birth" i]'],
    nome_mae: ['#nomeMae','[name*="mae" i]','[name*="mother" i]'],
    nome_pai: ['#nomePai','[name*="pai" i]','[name*="father" i]'],
    cep: ['#cep','[name*="cep" i]'], cidade: ['#cidade','[name*="cidade" i]','[name*="municipio" i]'],
    estado: ['#estado','[name="uf"]','[name*="estado" i]'], email: ['#email','input[type="email"]','[name*="email" i]'],
    telefone: ['#telefone','[name*="telefone" i]','[name*="celular" i]']
  };
  const setField = (key, value) => {
    if (!value) return false;
    for (const selector of (selectors[key] || [])) {
      const field = document.querySelector(selector);
      if (!field || field.disabled || field.readOnly) continue;
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
      if (setter) setter.call(field, value); else field.value = value;
      field.dispatchEvent(new Event('input', {bubbles: true}));
      field.dispatchEvent(new Event('change', {bubbles: true}));
      return true;
    }
    return false;
  };
  const fill = (data, clear = true) => {
    if (!data) return 0;
    let filled = 0;
    Object.keys(selectors).forEach((key) => { if (setField(key, data[key])) filled++; });
    if (filled) {
      const banner = document.createElement('div');
      banner.textContent = `M4: ${filled} campos preenchidos. Revise os dados e conclua manualmente.`;
      banner.style.cssText = 'position:fixed;z-index:2147483647;top:12px;right:12px;background:#14532d;color:#fff;padding:12px 16px;border-radius:8px;font:14px Arial;box-shadow:0 2px 8px #0005';
      document.body.appendChild(banner); setTimeout(() => banner.remove(), 7000);
      if (clear) chrome.storage.local.remove(['m4ClienteSelecionado', 'm4ClienteSelecionadoEm']);
    }
    return filled;
  };
  const fillFromStorage = () => chrome.storage.local.get(['m4ClienteSelecionado', 'm4ClienteSelecionadoEm']).then(({m4ClienteSelecionado: data, m4ClienteSelecionadoEm: savedAt}) => {
    if (!data || !savedAt || (Date.now() - savedAt) > 30 * 60 * 1000) return chrome.storage.local.remove(['m4ClienteSelecionado', 'm4ClienteSelecionadoEm']);
    fill(data);
  });
  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type === 'M4_FILL_NOW') fillFromStorage();
  });
  fillFromStorage();
})();
