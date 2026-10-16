const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const scriptPath = path.join(__dirname, '../../browser_extension/m4-certidoes/portal-fill.js');
const source = fs.readFileSync(scriptPath, 'utf8');

class FakeControl {
  constructor({tagName, type = 'text', name = '', id = '', label = '', placeholder = '', value = '', visible = true, parentText = '', options = [], maskDate = false}) {
    this.tagName = tagName;
    this.type = type;
    this.name = name;
    this.id = id;
    this.placeholder = placeholder;
    this.labels = label ? [{textContent: label}] : [];
    this.parentElement = {textContent: parentText};
    this.disabled = false;
    this.readOnly = false;
    this.offsetParent = visible ? {} : null;
    this._visible = visible;
    this._value = value;
    this.options = options;
    this.maskDate = maskDate;
    this.events = [];
  }

  get value() { return this._value; }
  set value(value) { this._value = String(value ?? ''); }
  getClientRects() { return this._visible ? [{}] : []; }
  getAttribute(attribute) {
    return ({'aria-label': this.ariaLabel, placeholder: this.placeholder}[attribute] ?? null);
  }
  dispatchEvent(event) {
    this.events.push(event.type);
    if (this.maskDate && event.type === 'input') {
      const digits = this._value.replace(/\D/g, '').slice(0, 8);
      this._value = digits.length > 4
        ? `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`
        : digits;
    }
    return true;
  }
}

class FakeInput extends FakeControl {}
class FakeSelect extends FakeControl {}
class FakeTextarea extends FakeControl {}

function makeDocument(fields) {
  return {
    body: {appendChild() {}},
    createElement(tagName) { return {tagName, style: {}, textContent: ''}; },
    querySelectorAll(selector) {
      if (selector === 'input, select, textarea') return fields;
      if (selector === 'input') return fields.filter((field) => field.tagName === 'INPUT');
      if (selector === 'select') return fields.filter((field) => field.tagName === 'SELECT');
      if (selector === 'input[type="text"], input:not([type])') {
        return fields.filter((field) => field.tagName === 'INPUT' && field.type === 'text');
      }
      return [];
    },
    querySelector() { return null; }
  };
}

async function runPortalFill(hostname, fields, payload) {
  const listeners = [];
  const now = Date.now();
  const context = {
    document: makeDocument(fields),
    location: {hostname},
    HTMLInputElement: FakeInput,
    HTMLSelectElement: FakeSelect,
    HTMLTextAreaElement: FakeTextarea,
    Event: class FakeEvent { constructor(type, options) { this.type = type; this.bubbles = options?.bubbles ?? false; } },
    Date,
    setTimeout() { return 1; },
    chrome: {
      storage: {local: {
        async get() { return {m4ClienteSelecionado: payload, m4ClienteSelecionadoEm: now}; },
        async remove() {}
      }},
      runtime: {onMessage: {addListener(listener) { listeners.push(listener); }}}
    }
  };
  vm.runInNewContext(source, context, {filename: scriptPath});
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(listeners.length, 1, 'content script registers its message listener');
  return new Promise((resolve) => {
    const keepsChannelOpen = listeners[0]({type: 'M4_FILL_NOW'}, {}, resolve);
    assert.equal(keepsChannelOpen, true);
  });
}

const client = {
  id: 12,
  nome: 'CLIENTE DE TESTE',
  cpf: '12345678900',
  rg: 'RG TESTE',
  rg_emissor: 'SSP/PI',
  data_nascimento: '1978-10-30',
  nome_pai: 'PAI FICTICIO',
  nome_mae: 'MAE FICTICIA',
  email: 'teste@example.invalid'
};

function hiddenQuformField(name, formText) {
  return new FakeInput({tagName: 'INPUT', type: 'hidden', name, visible: false, parentText: formText});
}

test('PCPI preenche controles visíveis e não conta metadados ocultos como sucesso', async () => {
  const wholeFormText = 'Tipo de Certidão Nome Completo Endereço de e-mail Filiação 01 Filiação 02 Nacionalidade Documento de Identificação Data de Nascimento CPF';
  const fields = [
    hiddenQuformField('quform_form_id', wholeFormText),
    hiddenQuformField('quform_csrf_token', wholeFormText),
    new FakeSelect({tagName: 'SELECT', name: 'quform_5_26', label: 'Tipo de Certidão', options: [
      {value: '', textContent: 'Selecione'},
      {value: 'antecedentes', textContent: 'Antecedentes Criminais'},
      {value: 'inquerito', textContent: 'Certidão de Inquérito Policial'}
    ]}),
    new FakeInput({tagName: 'INPUT', type: 'text', name: 'quform_5_3', label: 'Nome Completo*'}),
    new FakeInput({tagName: 'INPUT', type: 'email', name: 'quform_5_36', label: 'Endereço de e-mail*'}),
    new FakeInput({tagName: 'INPUT', type: 'text', name: 'quform_5_10', label: 'Filiação 01*'}),
    new FakeInput({tagName: 'INPUT', type: 'text', name: 'quform_5_11', label: 'Filiação 02'}),
    new FakeInput({tagName: 'INPUT', type: 'text', name: 'quform_5_15', label: 'Nacionalidade*'}),
    new FakeInput({tagName: 'INPUT', type: 'text', name: 'quform_5_17', label: 'Documento de Identificação'}),
    new FakeInput({tagName: 'INPUT', type: 'text', name: 'quform_5_18', label: 'Órgão Emissor'}),
    new FakeInput({tagName: 'INPUT', type: 'text', name: 'quform_5_25', label: 'Data de Nascimento*', placeholder: 'YYYY-MM-DD'}),
    new FakeInput({tagName: 'INPUT', type: 'text', name: 'quform_5_22', label: 'CPF'})
  ];

  const response = await runPortalFill('portal.pi.gov.br', fields, client);
  assert.equal(response.ok, true);
  assert.equal(response.filled, 10);
  assert.equal(fields[0].value, '', 'hidden form id remains untouched');
  assert.equal(fields[1].value, '', 'hidden token remains untouched');
  assert.equal(fields[2].value, 'antecedentes');
  assert.equal(fields[3].value, client.nome);
  assert.equal(fields[4].value, client.email);
  assert.equal(fields[5].value, client.nome_pai);
  assert.equal(fields[6].value, client.nome_mae);
  assert.equal(fields[7].value, 'Brasileiro');
  assert.equal(fields[8].value, client.rg);
  assert.equal(fields[9].value, client.rg_emissor);
  assert.equal(fields[10].value, '1978-10-30', 'PCPI date field advertises ISO format');
  assert.equal(fields[11].value, client.cpf);
});

test('PCPI informa nenhum campo compatível quando só há metadados ocultos', async () => {
  const fields = [hiddenQuformField('quform_form_id', 'Nome Completo Data de Nascimento CPF')];
  const response = await runPortalFill('portal.pi.gov.br', fields, client);
  assert.deepEqual({...response}, {ok: false, filled: 0});
  assert.equal(fields[0].value, '');
});

test('TSE preserva a data brasileira e não a sobrescreve com ISO no preenchimento genérico', async () => {
  const fields = [
    new FakeInput({tagName: 'INPUT', type: 'search', name: 'busca', placeholder: 'Busque um serviço'}),
    new FakeInput({tagName: 'INPUT', type: 'hidden', name: 'csrf', visible: false, parentText: 'Nome do eleitor CPF Data de nascimento Nome da mãe Nome do pai'}),
    new FakeInput({tagName: 'INPUT', type: 'text', name: 'nome_eleitor', label: 'Nome do eleitor'}),
    new FakeInput({tagName: 'INPUT', type: 'text', name: 'documento', label: 'Número do título eleitoral ou CPF'}),
    new FakeInput({tagName: 'INPUT', type: 'text', name: 'data_nascimento', label: 'Data de nascimento', maskDate: true}),
    new FakeInput({tagName: 'INPUT', type: 'text', name: 'nome_mae', label: 'Nome da mãe'}),
    new FakeInput({tagName: 'INPUT', type: 'text', name: 'nome_pai', label: 'Nome do pai'})
  ];

  const response = await runPortalFill('www.tse.jus.br', fields, client);
  assert.equal(response.ok, true);
  assert.equal(response.filled, 5);
  assert.equal(fields[0].value, '', 'global service search remains untouched');
  assert.equal(fields[1].value, '', 'hidden metadata remains untouched');
  assert.equal(fields[2].value, client.nome);
  assert.equal(fields[3].value, client.cpf);
  assert.equal(fields[4].value, '30/10/1978');
  assert.notEqual(fields[4].value, '19/78/1030');
  assert.equal(fields[5].value, client.nome_mae);
  assert.equal(fields[6].value, client.nome_pai);
});
