```javascript
// app/vendas/static/vendas/pdv_script.js

/**
 * =================================================================
 * ESTADO CENTRALIZADO DO CARRINHO
 * =================================================================
 */
const cartState = {
    saleId: null,
    clientId: null,
    clientName: 'Nenhum Cliente Selecionado',
    clientDocument: '',
    tempItem: null,
    items: [],
    subtotal: 0.00,
    discount: 0.00,
    total: 0.00
};

/**
 * =================================================================
 * UTILITÁRIOS GERAIS
 * =================================================================
 */
function showFeedback(message, type = 'danger') {
    const feedbackArea = $('#config-validation-feedback');
    feedbackArea.empty().append(`
        <div class="alert alert-${type} mt-3 mb-0" role="alert">
            ${message}
        </div>
    `);
}

/**
 * =================================================================
 * UTILITÁRIOS PARA NÚMEROS EM pt-BR
 * =================================================================
 */
function parseBrDecimal(str) {
    if (str === null || str === undefined) return NaN;
    let cleaned = String(str).trim();
    if (cleaned === '') return NaN;
    cleaned = cleaned.replace(/\./g, '');
    cleaned = cleaned.replace(',', '.');
    return parseFloat(cleaned);
}

function formatBrDecimal(num) {
    if (num === null || num === undefined || isNaN(num)) return '';
    return Number(num).toFixed(2).replace('.', ',');
}

/**
 * =================================================================
 * FUNÇÕES DE CÁLCULO E RENDERIZAÇÃO
 * =================================================================
 */
function calculateSummary() {
    let newSubtotal = 0.00;

    cartState.items.forEach(item => {
        newSubtotal += item.total_item || (item.quantity * item.unit_price);
    });

    cartState.subtotal = newSubtotal;
    cartState.total = Math.max(0, cartState.subtotal - cartState.discount);
}

function renderPDV() {
    calculateSummary();

    $('#summary-subtotal').text(`R$ ${cartState.subtotal.toFixed(2).replace('.', ',')}`);
    $('#summary-discount').text(`R$ ${cartState.discount.toFixed(2).replace('.', ',')}`);
    $('#summary-total').text(`R$ ${cartState.total.toFixed(2).replace('.', ',')}`);

    const clientDisplay = cartState.clientId
        ? `${cartState.clientName} (${cartState.clientDocument})`
        : 'Nenhum Cliente Selecionado';
    $('#selected-client-display').text(clientDisplay);

    const $tableBody = $('#cart-items-table tbody');
    $tableBody.empty();

    if (cartState.items.length === 0) {
        $tableBody.append(`<tr><td colspan="5" class="text-center text-muted">Adicione produtos para começar a venda.</td></tr>`);
        $('#finalize-sale-btn').prop('disabled', true);
    } else {
        cartState.items.forEach((item, index) => {
            const itemTotal = (item.quantity * item.unit_price).toFixed(2);
            let statusIcon = '';
            let actionsHtml = '';

            if (item.is_controlled) {
                const isConfigured = item.serial || item.lote || item.arma_cliente_id;
                const iconClass = isConfigured ? 'bi-check-circle-fill text-success' : 'bi-lock-fill text-danger';
                statusIcon = `<i class="bi ${iconClass} me-1" title="${isConfigured ? 'Item Configurado' : 'Requer Configuração'}"></i>`;

                actionsHtml = `
                    <button class="btn btn-sm btn-warning configure-item-btn" data-index="${index}" title="Configurar Lote/CRAF">
                        <i class="fas fa-cog me-1"></i> Configurar
                    </button>
                `;
            } else {
                actionsHtml = `
                    <button class="btn btn-sm btn-outline-danger remove-item-btn" data-index="${index}" title="Remover">
                        <i class="bi bi-trash"></i>
                    </button>
                `;
            }

            const row = `
                <tr data-item-index="${index}">
                    <td>${statusIcon} ${item.product_name}</td>
                    <td class="text-center">${item.quantity}</td>
                    <td class="text-end">R$ ${item.unit_price.toFixed(2).replace('.', ',')}</td>
                    <td class="text-end fw-bold">R$ ${itemTotal.replace('.', ',')}</td>
                    <td class="text-center">
                        ${actionsHtml}
                    </td>
                </tr>
            `;
            $tableBody.append(row);
        });
        $('#finalize-sale-btn').prop('disabled', false);
    }
}

/**
 * =================================================================
 * FUNÇÕES DE CLIENTE
 * =================================================================
 */
async function searchClients(query) {
    if (query.length < 3) {
        $('#client-search-results-area').html('<p class="text-muted text-center mt-4">Digite no mínimo 3 caracteres para iniciar a busca.</p>');
        return;
    }

    const url = `/vendas/api/clientes_autocomplete?q=${encodeURIComponent(query)}`;

    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Erro de rede: ${response.status}`);
        }
        const data = await response.json();
        renderClientResults(data);
    } catch (error) {
        console.error('Erro ao buscar clientes:', error);
        $('#client-search-results-area').html('<div class="alert alert-danger">Erro ao buscar clientes. Tente novamente.</div>');
    }
}

function renderClientResults(results) {
    const $resultsArea = $('#client-search-results-area');
    $resultsArea.empty();

    if (results.length === 0) {
        $resultsArea.append('<p class="text-muted text-center mt-4">Nenhum cliente encontrado.</p>');
        return;
    }

    results.forEach(client => {
        const statusClass = client.status === 'APROVADO' ? 'text-success' : 'text-warning';
        const item = `
            <a href="#" class="list-group-item list-group-item-action client-select-item"
               data-client-id="${client.id}"
               data-client-name="${client.nome}"
               data-client-doc="${client.documento}"
               data-client-cr="${client.cr}">
                <div class="d-flex w-100 justify-content-between">
                    <h6 class="mb-1">${client.nome}</h6>
                    <small class="${statusClass}">${client.status || 'VERIFICAR'}</small>
                </div>
                <p class="mb-1">Doc: ${client.documento}</p>
                <small>CR: ${client.cr}</small>
            </a>
        `;
        $resultsArea.append(item);
    });
}

function selectClient(clientId, name, document, cr) {
    cartState.clientId = clientId;
    cartState.clientName = name;
    cartState.clientDocument = document;

    renderPDV();
    $('#clientSearchModal').modal('hide');
}

/**
 * =================================================================
 * FUNÇÕES DE PRODUTO
 * =================================================================
 */
async function searchProducts(query) {
    if (query.length < 2) {
        $('#product-search-results').hide().empty();
        return;
    }

    const url = `/vendas/api/produtos_search?q=${encodeURIComponent(query)}`;

    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Erro de rede: ${response.status}`);
        }
        const data = await response.json();
        renderProductResults(data);
    } catch (error) {
        console.error('Erro ao buscar produtos:', error);
        $('#product-search-results').html('<div class="p-2 text-danger">Erro ao buscar produtos. (Verifique o servidor/DB)</div>').show();
    }
}

function renderProductResults(results) {
    const $resultsArea = $('#product-search-results');
    $resultsArea.empty();

    if (results.length === 0) {
        $resultsArea.append('<div class="p-2 text-muted">Nenhum produto encontrado.</div>').show();
        return;
    }

    results.forEach(product => {
        const stockStatusClass = product.estoque_disponivel > 0 ? 'bg-success' : 'bg-danger';
        const stockStatusText = product.estoque_disponivel > 0 ? `${product.estoque_disponivel} em estoque` : 'SEM ESTOQUE';

        const isControlled = product.is_controlled || product.is_controlado;
        const controlledIcon = isControlled
            ? `<i class="bi bi-lock-fill text-danger me-1" title="Item Controlado"></i>`
            : '';

        const priceDisplay = parseFloat(product.preco_venda).toFixed(2).replace('.', ',');

        const item = `
            <a href="#" class="list-group-item list-group-item-action product-select-item"
               data-product='${JSON.stringify(product)}'>
                <div class="d-flex w-100 justify-content-between">
                    <h6 class="mb-1">${controlledIcon} ${product.nome}</h6>
                    <span class="badge ${stockStatusClass}">${stockStatusText}</span>
                </div>
                <p class="mb-1">SKU: ${product.sku} | Preço: R$ ${priceDisplay}</p>
            </a>
        `;
        $resultsArea.append(item);
    });

    $resultsArea.show();
}

async function searchClientArmas(clientId, productCalibre) {
    const url = `/vendas/api/cliente/${clientId}/armas?calibre=${encodeURIComponent(productCalibre)}`;

    try {
        const response = await fetch(url);
        if (!response.ok) {
            console.error('Falha ao buscar armas do cliente.');
            return [];
        }
        return await response.json();
    } catch (error) {
        console.error('Erro de comunicação ao buscar armas:', error);
        return [];
    }
}

/**
 * =================================================================
 * FUNÇÕES DE CONFIGURAÇÃO DE ITEM
 * =================================================================
 */
async function configureItem(product, itemIndexToEdit = null) {
    let currentItem = itemIndexToEdit !== null ? cartState.items[itemIndexToEdit] : product;
    if (!currentItem) return;

    let unitPriceRaw = currentItem.unit_price != null ? currentItem.unit_price : currentItem.preco_venda;
    if (unitPriceRaw == null) unitPriceRaw = 0;
    let unitPriceNum = (typeof unitPriceRaw === 'number') ? unitPriceRaw : parseBrDecimal(unitPriceRaw);
    if (isNaN(unitPriceNum)) unitPriceNum = 0;

    cartState.tempItem = {
        product_id: currentItem.product_id || currentItem.id,
        product_name: currentItem.product_name || currentItem.nome,
        unit_price: unitPriceNum,
        quantity: currentItem.quantity || 1,
        is_controlled: (currentItem.is_controlled !== undefined ? currentItem.is_controlled : currentItem.is_controlado) || false,
        estoque_disponivel: currentItem.estoque_disponivel || 0,
        serial: currentItem.serial || '',
        lote: currentItem.lote || '',
        craf: currentItem.craf || '',
        arma_cliente_id: currentItem.arma_cliente_id || null,
        _index: itemIndexToEdit,
        calibre: currentItem.calibre || null
    };

    $('#product-search-results').hide().empty();
    $('#product-search-input').val('');

    $('#itemConfigModalLabel').text(`Configurar Item - ${cartState.tempItem.product_name}`);
    $('#item-config-name').text(cartState.tempItem.product_name);
    $('#config-quantity').val(cartState.tempItem.quantity);

    const formattedPrice = formatBrDecimal(cartState.tempItem.unit_price);
    $('#config-unit-price').val(formattedPrice);

    $('#config-validation-feedback').empty();

    const $stockStatus = $('#config-stock-status');
    const stock = cartState.tempItem.estoque_disponivel;
    $stockStatus.text(`Estoque: ${stock}`);
    $stockStatus.removeClass().addClass(`badge ${stock > 0 ? 'bg-success' : 'bg-danger'}`);

    if (cartState.tempItem.is_controlled) {
        $('#controlled-fields-area').show();
        $('#config-serial-lote').val(cartState.tempItem.serial || cartState.tempItem.lote);
        $('#config-craf').val(cartState.tempItem.craf);

        if (cartState.clientId && cartState.tempItem.calibre) {
            const armas = await searchClientArmas(cartState.clientId, cartState.tempItem.calibre);
            console.log('Armas encontradas:', armas);
        } else if (cartState.tempItem.is_controlled) {
            showFeedback('Item controlado. Para CRAF, selecione um cliente e o produto deve ter calibre definido.', 'info');
        }
    } else {
        $('#controlled-fields-area').hide();
    }

    const itemConfigModal = new bootstrap.Modal(document.getElementById('itemConfigModal'));
    itemConfigModal.show();
}

async function addItemToCart() {
    const tempItem = cartState.tempItem;

    const quantity = parseInt($('#config-quantity').val(), 10);
    const rawPriceInput = $('#config-unit-price').val();
    const price = parseBrDecimal(rawPriceInput);

    const serialLote = $('#config-serial-lote').val().trim();
    const craf = $('#config-craf').val().trim();
    const armaClienteId = null;

    if (!cartState.clientId) {
        showFeedback('Selecione um cliente antes de adicionar produtos.', 'warning');
        return;
    }
    if (isNaN(quantity) || quantity <= 0) {
        showFeedback('A quantidade deve ser um número positivo.', 'danger');
        return;
    }
    if (isNaN(price) || price <= 0) {
        showFeedback('O preço unitário deve ser um valor positivo e válido.', 'danger');
        return;
    }

    const payload = {
        client_id: cartState.clientId,
        product_id: tempItem.product_id,
        quantity: quantity,
        unit_price: price,
        is_controlled: tempItem.is_controlled,
        serial_lote: serialLote,
        craf: craf,
        arma_cliente_id: armaClienteId
    };

    const $addButton = $('#add-to-cart-btn');
    $addButton.prop('disabled', true).text('Adicionando...');

    try {
        const response = await fetch('/vendas/api/cart/add_item', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (response.ok) {
            if (tempItem._index !== null && tempItem._index !== undefined) {
                cartState.items[tempItem._index] = data.item;
            } else {
                cartState.items.push(data.item);
            }

            cartState.tempItem = null;
            renderPDV();
            $('#itemConfigModal').modal('hide');
        } else {
            showFeedback(data.error || 'Erro desconhecido ao validar o item.', 'danger');
        }
    } catch (error) {
        console.error('Erro na comunicação com o servidor:', error);
        showFeedback('Erro de comunicação com o servidor. Verifique sua conexão.', 'danger');
    } finally {
        $addButton.prop('disabled', false).text('Adicionar ao Carrinho');
    }
}

/**
 * =================================================================
 * FUNÇÕES DE FINALIZAÇÃO DE VENDA
 * =================================================================
 */
function openPaymentModal() {
    if (!cartState.clientId) {
        alert('Selecione um cliente para finalizar a venda.');
        return;
    }
    if (cartState.items.length === 0) {
        alert('Adicione itens ao carrinho para finalizar a venda.');
        return;
    }

    $('#payment-modal-total').text(`R$ ${cartState.total.toFixed(2).replace('.', ',')}`);
    $('#payment-modal-subtotal').text(`R$ ${cartState.subtotal.toFixed(2).replace('.', ',')}`);
    $('#payment-modal-discount').text(`R$ ${cartState.discount.toFixed(2).replace('.', ',')}`);

    $('#payment-received').val(cartState.total.toFixed(2));

    calculateChange();

    const paymentModal = new bootstrap.Modal(document.getElementById('paymentModal'));
    paymentModal.show();
}

function calculateChange() {
    const total = cartState.total;
    const received = parseBrDecimal($('#payment-received').val()) || 0;
    const change = received - total;

    $('#payment-change').text(`R$ ${formatBrDecimal(change)}`);

    if (change >= 0) {
        $('#confirm-payment-btn').prop('disabled', false).removeClass('btn-secondary').addClass('btn-success');
    } else {
        $('#confirm-payment-btn').prop('disabled', true).removeClass('btn-success').addClass('btn-secondary');
    }
}

async function finalizeSale() {
    const paymentReceived = parseBrDecimal($('#payment-received').val()) || 0;
    const paymentMethod = $('#payment-method').val();

    const payload = {
        client_id: cartState.clientId,
        items: cartState.items,
        subtotal: cartState.subtotal,
        discount: cartState.discount,
        total: cartState.total,
        payment_details: {
            method: paymentMethod,
            received: paymentReceived,
            change: paymentReceived - cartState.total
        }
    };

    $('#confirm-payment-btn').prop('disabled', true).text('Processando...');

    try {
        const response = await fetch('/vendas/api/cart/finalize_sale', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (response.ok) {
            alert(`Venda ${data.sale_id} finalizada com sucesso! Troco: R$ ${formatBrDecimal(payload.payment_details.change)}`);
            window.location.reload();
        } else {
            alert(`Erro ao finalizar venda: ${data.error || 'Erro desconhecido.'}`);
        }
    } catch (error) {
        console.error('Erro na comunicação com o servidor ao finalizar:', error);
        alert('Erro de comunicação com o servidor.');
    } finally {
        $('#confirm-payment-btn').prop('disabled', false).text('Confirmar Venda');
    }
}

/**
 * =================================================================
 * MANIPULADORES DE EVENTOS
 * =================================================================
 */
$(document).ready(function () {
    renderPDV();

    let clientSearchTimeout;
    let productSearchTimeout;

    $(document).on('click', '.remove-item-btn', function () {
        const indexToRemove = $(this).data('index');
        cartState.items.splice(indexToRemove, 1);
        renderPDV();
    });

    $(document).on('click', '.configure-item-btn', function () {
        const indexToEdit = $(this).data('index');
        const itemToEdit = cartState.items[indexToEdit];
        configureItem(itemToEdit, indexToEdit);
    });

    const $clientInput = $('#client-search-input');

    $clientInput.on('keyup', function () {
        clearTimeout(clientSearchTimeout);
        const query = $(this).val();
        clientSearchTimeout = setTimeout(() => { searchClients(query); }, 300);
    });

    $('#client-search-btn').on('click', function () { searchClients($clientInput.val()); });

    $(document).on('click', '.client-select-item', function (e) {
        e.preventDefault();
        const $item = $(this);
        selectClient($item.data('client-id'), $item.data('client-name'), $item.data('client-doc'), $item.data('client-cr'));
    });

    $('#clientSearchModal').on('shown.bs.modal', function () {
        $clientInput.trigger('focus');
        $('#client-search-results-area').empty();
    });

    const $productInput = $('#product-search-input');

    $productInput.on('keyup', function () {
        clearTimeout(productSearchTimeout);
        const query = $(this).val();

        if (query.length >= 2) {
            productSearchTimeout = setTimeout(() => {
                searchProducts(query);
            }, 300);
        } else {
            $('#product-search-results').hide().empty();
        }
    });

    $(document).on('click', '.product-select-item', function (e) {
        e.preventDefault();

        const rawProductJson = $(this).attr('data-product');

        try {
            const productData = JSON.parse(rawProductJson);
            configureItem(productData);
            $('#product-search-input').val('');
        } catch (error) {
            console.error('Erro ao fazer parse do JSON do produto:', error);
            console.log('JSON Bruto:', rawProductJson);
            alert('Erro interno: Falha ao carregar detalhes do produto. (Verifique se há aspas no nome do produto)');
        }
    });

    $('#add-to-cart-btn').on('click', function () {
        addItemToCart();
    });

    $('#config-unit-price').on('change', function () {
        const priceNum = parseBrDecimal($(this).val());
        if (!isNaN(priceNum) && priceNum > 0) {
            $(this).val(formatBrDecimal(priceNum));
        }
    });

    $('#scan-button').on('click', function () {
        $productInput.trigger('focus');
    });

    $('#finalize-sale-btn').on('click', function () {
        openPaymentModal();
    });

    $('#payment-received').on('keyup change', function () {
        calculateChange();
    });

    $('#confirm-payment-btn').on('click', function () {
        finalizeSale();
    });

    $('#save-draft-btn').on('click', function () {
        alert('Funcionalidade de Salvar Orçamento (Rascunho) será implementada em breve.');
    });
});
```

```html
{# app/vendas/templates/vendas/pdv_form.html #}
{% extends "base.html" %}

{% block content %}
<div class="container-fluid h-100 p-0">
    <div class="row g-0 h-100">

        <div class="col-12 col-lg-7 d-flex flex-column h-100 bg-light border-end">

            <header class="p-3 shadow-sm bg-white sticky-top">
                <div id="client-info-area" class="d-flex justify-content-between align-items-center">
                    <h5 class="mb-0 text-muted">
                        Cliente:
                        <span id="selected-client-display" class="fw-bold text-primary">
                            Nenhum Cliente Selecionado
                        </span>
                    </h5>
                    <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#clientSearchModal">
                        <i class="bi bi-search"></i> Buscar/Trocar Cliente
                    </button>
                </div>
            </header>

            <section id="product-search-area" class="p-3">
                <div class="input-group input-group-lg">
                    <input type="text" class="form-control" placeholder="Busque o produto por nome ou scaneie o código de barras..." id="product-search-input">
                    <button class="btn btn-success" type="button" id="scan-button" title="Ativar Scanner">
                        <i class="bi bi-qr-code-scan"></i>
                    </button>
                </div>
                <div id="product-search-results" class="position-absolute z-index-10 bg-white border w-50 shadow-lg mt-1" style="display: none;">
                </div>
            </section>

            <section id="cart-area" class="flex-grow-1 overflow-auto p-3">
                <h6 class="text-uppercase text-muted border-bottom pb-2">Itens no Carrinho</h6>
                <table class="table table-sm table-hover" id="cart-items-table">
                    <thead>
                        <tr>
                            <th>Produto</th>
                            <th class="text-center">Qtd</th>
                            <th class="text-end">Unitário</th>
                            <th class="text-end">Total</th>
                            <th class="text-center">Ações</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td colspan="5" class="text-center text-muted">
                                Adicione produtos para começar a venda.
                            </td>
                        </tr>
                    </tbody>
                </table>
            </section>
        </div>

        <div class="col-12 col-lg-5 d-flex flex-column h-100 bg-dark text-white p-4">

            <section id="financial-summary-area" class="mb-auto">
                <h4 class="mb-3">Resumo da Venda</h4>
                <div class="list-group list-group-flush mb-4">
                    <div class="list-group-item d-flex justify-content-between bg-dark text-white p-2">
                        <span>Subtotal:</span>
                        <span id="summary-subtotal">R$ 0,00</span>
                    </div>
                    <div class="list-group-item d-flex justify-content-between bg-dark text-white p-2">
                        <span>Desconto (<a href="#" id="apply-discount-link" class="text-info">Aplicar</a>):</span>
                        <span id="summary-discount">R$ 0,00</span>
                    </div>
                </div>

                <div class="p-3 bg-success rounded shadow-lg">
                    <h3 class="text-uppercase mb-1">Total Final</h3>
                    <h1 class="display-4 fw-bold" id="summary-total">R$ 0,00</h1>
                </div>
            </section>

            <section id="final-actions-area" class="mt-4 pt-3 border-top border-secondary">
                <button id="finalize-sale-btn" class="btn btn-primary btn-lg w-100 mb-2" disabled>
                    <i class="bi bi-wallet2"></i> Finalizar Venda (Pagamento)
                </button>
                <div class="d-flex justify-content-between">
                    <button id="save-draft-btn" class="btn btn-outline-light w-50 me-2">
                        <i class="bi bi-save"></i> Salvar Orçamento
                    </button>
                    <button id="cancel-sale-btn" class="btn btn-outline-danger w-50">
                        <i class="bi bi-x-circle"></i> Cancelar Venda
                    </button>
                </div>
            </section>
        </div>
    </div>
</div>

<div class="modal fade" id="clientSearchModal" tabindex="-1" aria-labelledby="clientSearchModalLabel" aria-hidden="true">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="clientSearchModalLabel">Buscar Cliente</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <div class="input-group mb-3">
                    <input type="text" class="form-control form-control-lg" placeholder="Nome, CPF ou CR do Cliente..." id="client-search-input">
                    <button class="btn btn-outline-secondary" type="button" id="client-search-btn">
                        <i class="bi bi-search"></i>
                    </button>
                </div>

                <div id="client-search-results-area" class="list-group">
                    <p class="text-muted text-center mt-4">Digite no mínimo 3 caracteres para iniciar a busca.</p>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fechar</button>
                <button type="button" class="btn btn-primary" id="new-client-btn">Novo Cliente</button>
            </div>
        </div>
    </div>
</div>

<div class="modal fade" id="itemConfigModal" tabindex="-1" aria-labelledby="itemConfigModalLabel" aria-hidden="true">
    <div class="modal-dialog modal-md">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="itemConfigModalLabel">Configurar Item</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <h4 id="item-config-name" class="mb-3 text-primary">Nome do Produto</h4>

                <div class="row g-3 mb-4">
                    <div class="col-md-6">
                        <label for="config-unit-price" class="form-label">Preço Unitário (R$)</label>
                        <input
                            type="text"
                            class="form-control form-control-lg"
                            id="config-unit-price"
                            inputmode="decimal"
                            autocomplete="off"
                            required
                        >
                    </div>
                    <div class="col-md-6">
                        <label for="config-quantity" class="form-label">Quantidade</label>
                        <input
                            type="number"
                            class="form-control form-control-lg"
                            id="config-quantity"
                            min="1"
                            value="1"
                        >
                    </div>
                </div>

                <div id="controlled-fields-area" style="display: none;" class="p-3 border rounded bg-light">
                    <p class="fw-bold text-danger">
                        <i class="bi bi-exclamation-triangle-fill"></i>
                        Item Controlado - Requer Documentação
                    </p>

                    <div class="mb-3">
                        <label for="config-serial-lote" class="form-label">Serial / Lote</label>
                        <input type="text" class="form-control" id="config-serial-lote" placeholder="Digite ou selecione o Serial/Lote" required>
                    </div>

                    <div class="mb-0">
                        <label for="config-craf" class="form-label">CRAF (Se aplicável)</label>
                        <input type="text" class="form-control" id="config-craf" placeholder="Vincular CRAF do Cliente">
                    </div>
                </div>

                <div id="config-validation-feedback" class="mt-3">
                    <span id="config-stock-status" class="badge bg-secondary">Estoque: 0</span>
                </div>

            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                <button type="button" class="btn btn-primary" id="add-to-cart-btn">
                    <i class="bi bi-cart-plus"></i> Adicionar ao Carrinho
                </button>
            </div>
        </div>
    </div>
</div>

<div class="modal fade" id="paymentModal" tabindex="-1" aria-labelledby="paymentModalLabel" aria-hidden="true">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header bg-primary text-white">
                <h5 class="modal-title" id="paymentModalLabel">
                    <i class="bi bi-wallet2"></i> Finalizar Venda
                </h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <div class="row">
                    <div class="col-md-6 mb-3">
                        <h4 class="text-muted">Total a Pagar</h4>
                        <h1 class="display-3 fw-bold text-success" id="payment-modal-total">R$ 0,00</h1>
                        <hr>
                        <p class="mb-1">
                            Subtotal:
                            <span id="payment-modal-subtotal">R$ 0,00</span>
                        </p>
                        <p class="mb-0">
                            Desconto:
                            <span id="payment-modal-discount">R$ 0,00</span>
                        </p>
                    </div>

                    <div class="col-md-6">
                        <label for="payment-method" class="form-label fw-bold">Forma de Pagamento</label>
                        <select class="form-select form-select-lg mb-3" id="payment-method">
                            <option value="DINHEIRO" selected>Dinheiro</option>
                            <option value="CARTAO_DEB">Cartão de Débito</option>
                            <option value="CARTAO_CRED">Cartão de Crédito</option>
                            <option value="PIX">PIX</option>
                            <option value="TRANSFERENCIA">Transferência</option>
                        </select>

                        <label for="payment-received" class="form-label fw-bold">Valor Recebido (R$)</label>
                        <input type="number" class="form-control form-control-lg mb-3" id="payment-received" step="0.01" min="0">

                        <div class="alert alert-info mt-4" role="alert">
                            Troco: <span class="fw-bold" id="payment-change">R$ 0,00</span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Voltar</button>
                <button type="button" class="btn btn-success btn-lg" id="confirm-payment-btn" disabled>
                    <i class="bi bi-check-circle-fill"></i> Confirmar Venda
                </button>
            </div>
        </div>
    </div>
</div>

{% endblock %}

{% block scripts %}
    {{ super() }}
    <script src="{{ url_for('vendas.static', filename='vendas/pdv_script.js') }}"></script>
{% endblock %}

