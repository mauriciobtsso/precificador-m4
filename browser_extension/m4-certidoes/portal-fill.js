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

  const visibleEditableField = (field) => {
    if (!field || field.disabled || field.readOnly) return false;
    if (['hidden', 'file', 'search', 'password', 'submit', 'button', 'reset', 'checkbox', 'radio'].includes(field.type)) return false;
    if (field.getAttribute?.('aria-hidden') === 'true') return false;
    if (field.getClientRects && field.getClientRects().length === 0) return false;
    return field.offsetParent !== null || Boolean(field.getClientRects?.().length);
  };

  const rotuloDoCampo = (field) => norm([
    field.name,
    field.id,
    field.getAttribute('aria-label'),
    field.getAttribute('placeholder'),
    ...(field.labels ? [...field.labels].map((label) => label.textContent) : [])
  ].filter(Boolean).join(' '));

  const parseDate = (value) => {
    const text = String(value || '').trim();
    let match = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:$|T)/);
    let year;
    let month;
    let day;
    if (match) {
      [, year, month, day] = match;
    } else if ((match = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/))) {
      [, day, month, year] = match;
    } else if ((match = text.match(/^(\d{4})(\d{2})(\d{2})$/))) {
      [, year, month, day] = match;
    } else {
      return null;
    }

    const yyyy = Number(year);
    const mm = Number(month);
    const dd = Number(day);
    const date = new Date(Date.UTC(yyyy, mm - 1, dd));
    if (date.getUTCFullYear() !== yyyy || date.getUTCMonth() !== mm - 1 || date.getUTCDate() !== dd) return null;

    return {
      iso: `${String(yyyy).padStart(4, '0')}-${String(mm).padStart(2, '0')}-${String(dd).padStart(2, '0')}`,
      br: `${String(dd).padStart(2, '0')}/${String(mm).padStart(2, '0')}/${String(yyyy).padStart(4, '0')}`
    };
  };

  const dataForDateField = (field, value) => {
    const parsed = parseDate(value);
    if (!parsed) return '';
    const placeholder = norm(field.getAttribute('placeholder'));
    return field.type === 'date' || /yyyy-mm-dd/.test(placeholder) ? parsed.iso : parsed.br;
  };

  const valueMatches = (actual, expected) => {
    const actualText = String(actual ?? '').trim();
    const expectedText = String(expected ?? '').trim();
    if (!actualText || !expectedText) return false;
    if (norm(actualText).replace(/\s+/g, ' ') === norm(expectedText).replace(/\s+/g, ' ')) return true;
    const expectedDigits = expectedText.replace(/\D/g, '');
    return expectedDigits.length > 0 && /^\d+$/.test(expectedText) && actualText.replace(/\D/g, '') === expectedDigits;
  };

  const setNativeValue = (field, value) => {
    if (!field || value === undefined || value === null || String(value).trim() === '') return false;
    if (!visibleEditableField(field)) return false;

    const tagName = field.tagName?.toUpperCase();
    const prototype = tagName === 'SELECT'
      ? HTMLSelectElement.prototype
      : tagName === 'TEXTAREA'
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
    try {
      if (setter) setter.call(field, String(value));
      else field.value = String(value);
    } catch (_) {
      return false;
    }

    field.dispatchEvent(new Event('input', {bubbles: true}));
    field.dispatchEvent(new Event('change', {bubbles: true}));
    return valueMatches(field.value, value);
  };

  const setPorRotulo = (padroes, valor, formatar = (field, value) => value) => {
    if (valor === undefined || valor === null || String(valor).trim() === '') return false;
    const campo = [...document.querySelectorAll('input, select, textarea')]
      .filter(visibleEditableField)
      .find((field) => padroes.some((padrao) => padrao.test(rotuloDoCampo(field))));
    if (!campo) return false;
    return setNativeValue(campo, formatar(campo, valor));
  };

  const payloadValue = (data, key) => ({
    orgao_expedidor: data.rg_emissor || data.orgao_expedidor,
    endereco: data.logradouro || data.endereco,
    cidade: data.cidade || data.municipio,
    estado: data.uf || data.estado,
    mae: data.nome_mae || data.mae,
    pai: data.nome_pai || data.pai
  }[key] ?? data[key]);

  const preencherPcPi = (data) => {
    if (location.hostname !== 'portal.pi.gov.br') return 0;
    let filled = 0;
    const campos = [
      [[/nome completo/], data.nome || data.nome_completo],
      [[/endereco de e-mail/], data.email],
      [[/filia[cç][aã]o 01/], data.nome_pai],
      [[/filia[cç][aã]o 02/], data.nome_mae],
      [[/nacionalidade/], 'Brasileiro'],
      [[/documento de identifica[cç][aã]o/], data.rg],
      [[/org[aã]o emissor/], data.rg_emissor],
      [[/\bcpf\b/], data.cpf],
      [[/data de nascimento/], data.data_nascimento]
    ];
    campos.forEach(([padroes, valor]) => {
      const formatar = padroes[0].source === 'data de nascimento'
        ? dataForDateField
        : (field, input) => input;
      if (setPorRotulo(padroes, valor, formatar)) filled++;
    });

    const tipo = [...document.querySelectorAll('select')]
      .filter(visibleEditableField)
      .find((field) => /tipo de certidao/.test(rotuloDoCampo(field)));
    if (tipo) {
      const option = [...tipo.options].find((item) => /antecedentes criminais/i.test(norm(item.textContent)));
      if (option && setNativeValue(tipo, option.value)) filled++;
    }
    return filled;
  };

  const tseInputs = () => {
    const visible = [...document.querySelectorAll('input')]
      .filter(visibleEditableField)
      .filter((field) => !/busque um servico|qual servico voce procura/.test(rotuloDoCampo(field)));
    const forms = [...document.querySelectorAll('form')]
      .map((form) => [...form.querySelectorAll('input')].filter(visibleEditableField))
      .filter((fields) => fields.length >= 5);
    return forms.sort((a, b) => a.length - b.length)[0] || visible;
  };

  const preencherTse = (data) => {
    if (location.hostname !== 'www.tse.jus.br' && !location.hostname.endsWith('.tse.jus.br')) return 0;
    const fields = tseInputs();
    if (fields.length < 5) return 0;

    const tarefas = [
      {patterns: [/nome do eleitor/, /nome completo/], value: data.nome || data.nome_completo, index: 0},
      {patterns: [/numero do titulo eleitoral/, /titulo eleitoral.*cpf/, /\bcpf\b/], value: data.cpf || data.documento, index: 1},
      {patterns: [/data de nascimento/], value: data.data_nascimento, index: 2, format: dataForDateField},
      {patterns: [/nome da mae/, /nome materno/, /filiacao.*mae/], value: data.nome_mae, index: 3},
      {patterns: [/nome do pai/, /nome paterno/, /filiacao.*pai/], value: data.nome_pai, index: 4}
    ];

    let filled = 0;
    const used = new Set();
    tarefas.forEach((task) => {
      if (task.value === undefined || task.value === null || String(task.value).trim() === '') return;
      const byLabel = fields.find((field) => !used.has(field) && task.patterns.some((pattern) => pattern.test(rotuloDoCampo(field))));
      const target = byLabel || fields[task.index];
      if (!target || used.has(target)) return;
      const value = task.format ? task.format(target, task.value) : task.value;
      if (setNativeValue(target, value)) {
        used.add(target);
        filled++;
      }
    });
    return filled;
  };

  const fillStmLegacy = (data) => {
    if (!location.hostname.includes('stm.jus.br')) return 0;
    const inputs = [...document.querySelectorAll('input[type="text"], input:not([type])')]
      .filter(visibleEditableField);
    if (inputs.length < 9) return 0;
    const cpf = String(data.cpf || data.documento || '').replace(/\D/g, '').padStart(11, '0');
    const nascimento = parseDate(data.data_nascimento);
    const dataFormatada = nascimento ? [nascimento.br.slice(0, 2), nascimento.br.slice(3, 5), nascimento.br.slice(6, 10)] : ['', '', ''];
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

    const host = location.hostname;
    const portalEspecifico = host === 'portal.pi.gov.br' || host === 'www.tse.jus.br' || host.endsWith('.tse.jus.br') || host.includes('stm.jus.br');
    if (!portalEspecifico) {
      Object.keys(selectors).forEach((key) => {
        const value = payloadValue(data, key);
        if (!value) return;
        const field = (selectors[key] || []).map((selector) => {
          try { return document.querySelector(selector); } catch (_) { return null; }
        }).find(visibleEditableField);
        if (!field) return;
        const fieldValue = key === 'data_nascimento' ? dataForDateField(field, value) : value;
        if (setNativeValue(field, fieldValue)) filled++;
      });
    }

    const cep = [...document.querySelectorAll('input[formcontrolname="cep"]')].find(visibleEditableField);
    if (cep && payloadValue(data, 'cep')) cep.dispatchEvent(new Event('blur', {bubbles: true}));

    if (filled) {
      const banner = document.createElement('div');
      banner.textContent = `M4: ${filled} campos preenchidos e verificados. Revise os dados e conclua manualmente.`;
      banner.style.cssText = 'position:fixed;z-index:2147483647;top:12px;right:12px;background:#14532d;color:#fff;padding:12px 16px;border-radius:8px;font:14px Arial;box-shadow:0 2px 8px #0005';
      document.body.appendChild(banner);
      setTimeout(() => banner.remove(), 7000);
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
