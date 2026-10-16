(() => {
  const norm = (value) => (value || '').toString().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const selectors = {
    cpf: ['input[formcontrolname="cpf"]','#cpf','[name="cpf"]','[name*="cpf" i]','[id*="cpf" i]','[name*="documento" i]'],
    nome: ['input[formcontrolname="requerente"]','#nome','[name="nome"]','[name*="nome" i]','[name*="name" i]'],
    rg: ['input[formcontrolname="rg"]','#rg','[name="rg"]','[name*="rg" i]'],
    data_nascimento: ['#dataNascimento','[name*="nascimento" i]','[name*="birth" i]'],
    nome_mae: ['input[formcontrolname="mae"]','#nomeMae','[name*="mae" i]','[name*="mother" i]'],
    nome_pai: ['input[formcontrolname="pai"]','#nomePai','[name*="pai" i]','[name*="father" i]'],
    cep: ['input[formcontrolname="cep"]','#cep','[name*="cep" i]'],
    cidade: ['input[formcontrolname="municipio"]','#cidade','[name*="cidade" i]','[name*="municipio" i]'],
    estado: ['input[formcontrolname="uf"]','#estado','[name="uf"]','[name*="estado" i]'],
    email: ['#email','input[type="email"]','[name*="email" i]'],
    telefone: ['#telefone','[name*="telefone" i]','[name*="celular" i]'],
    orgao_expedidor: ['input[formcontrolname="orgaoExpedidor"]','[name*="orgaoExpedidor" i]'],
    endereco: ['input[formcontrolname="endereco"]','[name*="endereco" i]'],
    numero: ['input[formcontrolname="numero"]','[name="numero"]'],
    complemento: ['input[formcontrolname="complemento"]','[name="complemento"]'],
    bairro: ['input[formcontrolname="bairro"]','[name*="bairro" i]']
  };
  const setField = (key, value) => {
    if (!value) return false;
    for (const selector of (selectors[key] || [])) {
      const field = document.querySelector(selector);
      if (!field || field.disabled || field.readOnly) continue;
      const prototype = field instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
      if (setter) setter.call(field, value); else field.value = value;
      field.dispatchEvent(new Event('input', {bubbles: true}));
      field.dispatchEvent(new Event('change', {bubbles: true}));
      return true;
    }
    return false;
  };
  const payloadValue = (data, key) => ({
    orgao_expedidor: data.rg_emissor || data.orgao_expedidor,
    endereco: data.logradouro || data.endereco,
    cidade: data.cidade || data.municipio,
    estado: data.uf || data.estado,
    mae: data.nome_mae || data.mae,
    pai: data.nome_pai || data.pai
  }[key] ?? data[key]);
  const setNativeValue = (field, value) => {
    if (!field || value === undefined || value === null) return false;
    const prototype = field instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
    if (setter) setter.call(field, value); else field.value = value;
    field.dispatchEvent(new Event('input', {bubbles: true}));
    field.dispatchEvent(new Event('change', {bubbles: true}));
    return true;
  };
  const rotuloDoCampo = (field) => norm([
    field.name, field.id, field.getAttribute('aria-label'), field.getAttribute('placeholder'),
    field.labels?.[0]?.textContent, field.parentElement?.textContent
  ].filter(Boolean).join(' '));
  const setPorRotulo = (padroes, valor) => {
    if (!valor) return false;
    const campo = [...document.querySelectorAll('input, select, textarea')]
      .filter((field) => !field.disabled && !field.readOnly)
      .find((field) => padroes.some((padrao) => padrao.test(rotuloDoCampo(field))));
    return setNativeValue(campo, valor);
  };
  const preencherPcPi = (data) => {
    if (!location.hostname.includes('portal.pi.gov.br')) return 0;
    let filled = 0;
    if (setPorRotulo([/nome completo/], data.nome)) filled++;
    if (setPorRotulo([/endereco de e-mail/], data.email)) filled++;
    if (setPorRotulo([/filia[cç][aã]o 01/], data.nome_pai)) filled++;
    if (setPorRotulo([/filia[cç][aã]o 02/], data.nome_mae)) filled++;
    if (setPorRotulo([/nacionalidade/], 'Brasileiro')) filled++;
    if (setPorRotulo([/documento de identifica[cç][aã]o/], data.rg)) filled++;
    if (setPorRotulo([/org[aã]o emissor/], data.rg_emissor)) filled++;
    if (setPorRotulo([/cpf/], data.cpf)) filled++;
    if (setPorRotulo([/data de nascimento/], data.data_nascimento)) filled++;
    const tipo = [...document.querySelectorAll('select')].find((field) => /tipo de certid[aã]o/.test(rotuloDoCampo(field)));
    if (tipo) {
      const option = [...tipo.options].find((item) => /negativa/i.test(norm(item.textContent)));
      if (option && setNativeValue(tipo, option.value)) filled++;
    }
    return filled;
  };
  const preencherTse = (data) => {
    if (!location.hostname.includes('tse.jus.br')) return 0;
    const inputs = [...document.querySelectorAll('input')]
      .filter((field) => !field.disabled && !field.readOnly && field.type !== 'search' && field.offsetParent !== null && !/busque um servi[cç]o/i.test(rotuloDoCampo(field)));
    if (inputs.length < 5) return 0;
    const nascimento = String(data.data_nascimento || '').split('-');
    const dataFormatada = nascimento.length === 3 ? `${nascimento[2]}/${nascimento[1]}/${nascimento[0]}` : '';
    let filled = 0;
    [[0, data.nome], [1, data.cpf], [2, dataFormatada], [3, data.nome_mae], [4, data.nome_pai]]
      .forEach(([index, value]) => { if (setNativeValue(inputs[index], value)) filled++; });
    return filled;
  };
  const fillStmLegacy = (data) => {
    if (!location.hostname.includes('stm.jus.br')) return 0;
    const inputs = [...document.querySelectorAll('input[type="text"], input:not([type])')]
      .filter((field) => !field.disabled && !field.readOnly);
    if (inputs.length < 9) return 0;
    const cpf = String(data.cpf || data.documento || '').replace(/\D/g, '').padStart(11, '0');
    const nascimento = String(data.data_nascimento || '').split('-');
    const dataFormatada = nascimento.length === 3 ? [nascimento[2], nascimento[1], nascimento[0]] : ['', '', ''];
    let filled = 0;
    if (setNativeValue(inputs[0], data.nome || data.nome_completo)) filled++;
    [[1, cpf.slice(0, 3)], [2, cpf.slice(3, 6)], [3, cpf.slice(6, 9)], [4, cpf.slice(9, 11)]]
      .forEach(([index, value]) => { if (setNativeValue(inputs[index], value)) filled++; });
    dataFormatada.forEach((value, offset) => { if (value && setNativeValue(inputs[5 + offset], value)) filled++; });
    if (setNativeValue(inputs[8], data.nome_mae)) filled++;
    return filled;
  };
  const selecionarTjpi = async (formcontrolname, texto) => {
    if (!location.hostname.includes('tjpi.jus.br')) return 0;
    const trigger = document.querySelector(`mat-select[formcontrolname="${formcontrolname}"]`);
    if (!trigger) return 0;
    const atual = norm(trigger.textContent);
    if (atual.includes(norm(texto))) return 0;
    trigger.click();
    const alvo = norm(texto);
    for (let tentativa = 0; tentativa < 20; tentativa++) {
      const opcao = [...document.querySelectorAll('mat-option')]
        .find((item) => norm(item.textContent).includes(alvo));
      if (opcao) { opcao.click(); return 1; }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    return 0;
  };
  const fill = async (data, clear = true) => {
    if (!data) return 0;
    let filled = fillStmLegacy(data) + preencherPcPi(data) + preencherTse(data);
    filled += await selecionarTjpi('tipoParte', 'PESSOA FÍSICA');
    filled += await selecionarTjpi('grauJuridicao', 'AMBAS');
    filled += await selecionarTjpi('tipoCertidao', 'Negativa Criminal e Auditoria Militar');
    Object.keys(selectors).forEach((key) => { if (setField(key, payloadValue(data, key))) filled++; });
    if (document.querySelector('input[formcontrolname="cep"]') && payloadValue(data, 'cep')) {
      const cep = document.querySelector('input[formcontrolname="cep"]');
      cep.dispatchEvent(new Event('blur', {bubbles: true}));
    }
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
    if (!data || !savedAt || (Date.now() - savedAt) > 30 * 60 * 1000) {
      return chrome.storage.local.remove(['m4ClienteSelecionado', 'm4ClienteSelecionadoEm']).then(() => 0);
    }
    return fill(data, false);
  });
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === 'M4_FILL_NOW') {
      fillFromStorage().then((filled) => sendResponse({ok: filled > 0, filled})).catch(() => sendResponse({ok: false, filled: 0}));
      return true;
    }
  });
  fillFromStorage();
})();
