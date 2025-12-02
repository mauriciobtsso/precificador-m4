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
    
    // Objeto temporário para o item sendo configurado no modal
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

// Função para exibir feedback (pode ser substituída por um Toast/Notificação do Bootstrap)
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
 * FUNÇÕES DE CÁLCULO E RENDERIZAÇÃO
 * =================================================================
 */
function calculateSummary() {
    let newSubtotal = 0.00;
    
    cartState.items.forEach(item => {
        // Usa o total_item se o backend o retornar, ou recalcula
        newSubtotal += item.total_item || (item.quantity * item.unit_price);
    });

    cartState.subtotal = newSubtotal;
    cartState.total = Math.max(0, cartState.subtotal - cartState.discount);
}

function renderPDV() {
    calculateSummary();

    // 1. Atualiza o Resumo Financeiro
    $('#summary-subtotal').text(`R$ ${cartState.subtotal.toFixed(2).replace('.', ',')}`);
    $('#summary-discount').text(`R$ ${cartState.discount.toFixed(2).replace('.', ',')}`);
    $('#summary-total').text(`R$ ${cartState.total.toFixed(2).replace('.', ',')}`);

    // 2. Atualiza o Display do Cliente
    const clientDisplay = cartState.clientId ? 
        `${cartState.clientName} (${cartState.clientDocument})` : 
        'Nenhum Cliente Selecionado';
    $('#selected-client-display').text(clientDisplay);
    
    // 3. Renderiza a Tabela do Carrinho
    const $tableBody = $('#cart-items-table tbody');
    $tableBody.empty(); 

    if (cartState.items.length === 0) {
        $tableBody.append(`<tr><td colspan="5" class="text-center text-muted">Adicione produtos para começar a venda.</td></tr>`);
        $('#finalize-sale-btn').prop('disabled', true);
    } else {
        cartState.items.forEach((item, index) => {
            const itemTotal = (item.quantity * item.unit_price).toFixed(2);
            let statusIcon = '';
            
            if (item.is_controlled) {
                // Se for controlado E tiver serial/lote preenchido, use um ícone de verificação
                const iconClass = item.serial || item.lote ? 'bi-check-circle-fill text-success' : 'bi-lock-fill text-danger';
                statusIcon = `<i class="bi ${iconClass} me-1" title="Item Controlado"></i>`;
            }

            const row = `
                <tr data-item-index="${index}">
                    <td>${statusIcon} ${item.product_name}</td>
                    <td class="text-center">${item.quantity}</td>
                    <td class="text-end">R$ ${item.unit_price.toFixed(2).replace('.', ',')}</td>
                    <td class="text-end fw-bold">R$ ${itemTotal.replace('.', ',')}</td>
                    <td class="text-center">
                        <button class="btn btn-sm btn-outline-danger remove-item-btn" data-index="${index}" title="Remover">
                            <i class="bi bi-trash"></i>
                        </button>
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
        $('#product-search-results').html('<div class="p-2 text-danger">Erro ao buscar produtos.</div>').show();
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
        const stockStatusText = product.estoque_disponivel > 0 ? `${product.estoque_disponivel} em estoque` : `SEM ESTOQUE`;

        const controlledIcon = product.is_controlado ? 
            `<i class="bi bi-lock-fill text-danger me-1" title="Item Controlado"></i>` : '';

        const item = `
            <a href="#" class="list-group-item list-group-item-action product-select-item" 
               data-product='${JSON.stringify(product)}'>
                <div class="d-flex w-100 justify-content-between">
                    <h6 class="mb-1">${controlledIcon} ${product.nome}</h6>
                    <span class="badge ${stockStatusClass}">${stockStatusText}</span>
                </div>
                <p class="mb-1">SKU: ${product.sku} | Preço: R$ ${product.preco_venda.toFixed(2).replace('.', ',')}</p>
            </a>
        `;
        $resultsArea.append(item);
    });

    $resultsArea.show();
}

/**
 * =================================================================
 * FUNÇÕES DE CONFIGURAÇÃO DE ITEM (Ações 8 & 9 da Fase 3)
 * =================================================================
 */

// Função que preenche o modal com o item selecionado
function configureItem(product) {
    // 1. Armazena o produto selecionado temporariamente no estado
    cartState.tempItem = {
        product_id: product.id,
        product_name: product.nome,
        unit_price: product.preco_venda,
        quantity: 1, 
        is_controlled: product.is_controlado,
        estoque_disponivel: product.estoque_disponivel,
        // Campos complexos iniciais:
        serial: '',
        lote: '',
        craf: ''
    };
    
    // 2. Oculta os resultados da busca e limpa o input
    $('#product-search-results').hide().empty();
    $('#product-search-input').val('');
    
    // 3. Preenche os campos do Modal
    $('#itemConfigModalLabel').text(`Configurar Item`);
    $('#item-config-name').text(product.nome);
    $('#config-quantity').val(cartState.tempItem.quantity);
    $('#config-unit-price').val(cartState.tempItem.unit_price.toFixed(2));
    
    // 4. Limpa feedbacks anteriores
    $('#config-validation-feedback').empty();

    // 5. Atualiza o status de estoque
    const $stockStatus = $('#config-stock-status');
    const stock = cartState.tempItem.estoque_disponivel;
    $stockStatus.text(`Estoque: ${stock}`);
    $stockStatus.removeClass().addClass(`badge ${stock > 0 ? 'bg-success' : 'bg-danger'}`);
    
    // 6. Mostra/Esconde campos controlados
    if (cartState.tempItem.is_controlled) {
        $('#controlled-fields-area').show();
        // Limpa inputs de controle (para novo item)
        $('#config-serial-lote').val('');
        $('#config-craf').val('');
    } else {
        $('#controlled-fields-area').hide();
    }
    
    // 7. Abre o modal
    const itemConfigModal = new bootstrap.Modal(document.getElementById('itemConfigModal'));
    itemConfigModal.show();
}

// Função que move o item temporário para o carrinho via chamada de API (Ação 9)
async function addItemToCart() {
    const tempItem = cartState.tempItem;
    
    // 1. Coleta os valores atuais do formulário do modal
    const quantity = parseInt($('#config-quantity').val());
    const price = parseFloat($('#config-unit-price').val());
    const serialLote = $('#config-serial-lote').val().trim();
    const craf = $('#config-craf').val().trim();
    
    // 2. Validação local básica (evita chamada de API desnecessária)
    if (!cartState.clientId) {
        showFeedback('Selecione um cliente antes de adicionar produtos.', 'warning');
        return;
    }
    if (isNaN(quantity) || quantity <= 0) {
        showFeedback('A quantidade deve ser um número positivo.', 'danger');
        return;
    }
    if (isNaN(price) || price <= 0) {
        showFeedback('O preço unitário deve ser um valor positivo.', 'danger');
        return;
    }
    
    // 3. Monta o payload de dados para o backend
    const payload = {
        client_id: cartState.clientId,
        product_id: tempItem.product_id,
        quantity: quantity,
        unit_price: price,
        is_controlled: tempItem.is_controlled,
        serial_lote: serialLote,
        craf: craf
        // Outros dados importantes podem ser adicionados aqui
    };
    
    // 4. Chamada AJAX/Fetch para o endpoint de validação/adição (POST)
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
            // Sucesso na validação e adição (backend retornou 200)
            
            // 5. Adiciona o item final (validado pelo backend) ao estado local
            cartState.items.push(data.item);
            
            // 6. Limpa e atualiza a UI
            cartState.tempItem = null;
            renderPDV(); 
            $('#itemConfigModal').modal('hide'); 
            // Feedback de sucesso (opcional)
            // showFeedback(`Item ${data.item.product_name} adicionado com sucesso!`, 'success'); 

        } else {
            // Erro de validação de negócio (backend retornou 400 ou 404)
            showFeedback(data.error || 'Erro desconhecido ao validar o item.', 'danger');
        }

    } catch (error) {
        console.error('Erro na comunicação com o servidor:', error);
        showFeedback('Erro de comunicação com o servidor. Verifique sua conexão.', 'danger');
    }
}

/**
 * =================================================================
 * FUNÇÕES DE FINALIZAÇÃO DE VENDA (Ação 11 da Fase 3)
 * =================================================================
 */

// Função que abre o modal e preenche os totais
function openPaymentModal() {
    if (!cartState.clientId) {
        alert('Selecione um cliente para finalizar a venda.');
        return;
    }
    if (cartState.items.length === 0) {
        alert('Adicione itens ao carrinho para finalizar a venda.');
        return;
    }

    // Garante que os valores no modal reflitam o total atual
    $('#payment-modal-total').text(`R$ ${cartState.total.toFixed(2).replace('.', ',')}`);
    $('#payment-modal-subtotal').text(`R$ ${cartState.subtotal.toFixed(2).replace('.', ',')}`);
    $('#payment-modal-discount').text(`R$ ${cartState.discount.toFixed(2).replace('.', ',')}`);
    
    // Define o valor recebido inicial como o valor total (pagamento exato)
    $('#payment-received').val(cartState.total.toFixed(2));
    
    // Força o cálculo inicial do troco
    calculateChange();
    
    const paymentModal = new bootstrap.Modal(document.getElementById('paymentModal'));
    paymentModal.show();
}

// Calcula o troco e habilita/desabilita o botão de confirmação
function calculateChange() {
    const total = cartState.total;
    const received = parseFloat($('#payment-received').val().replace(',', '.')) || 0;
    const change = received - total;

    $('#payment-change').text(`R$ ${change.toFixed(2).replace('.', ',')}`);
    
    // Habilita o botão se o valor recebido for suficiente
    if (change >= 0) {
        $('#confirm-payment-btn').prop('disabled', false).removeClass('btn-secondary').addClass('btn-success');
    } else {
        $('#confirm-payment-btn').prop('disabled', true).removeClass('btn-success').addClass('btn-secondary');
    }
}

// Função que envia o carrinho e o pagamento para o backend
async function finalizeSale() {
    const paymentReceived = parseFloat($('#payment-received').val().replace(',', '.')) || 0;
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
            alert(`Venda ${data.sale_id} finalizada com sucesso! Troco: R$ ${(payload.payment_details.change).toFixed(2).replace('.', ',')}`);
            
            // TODO: Redirecionar para a tela de Recibo/PDF
            window.location.reload(); // Recarrega a página para nova venda
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

// ... (bloco $(document).ready)

$(document).ready(function() {
    // ... (código existente) ...

    // ----------------------------------------------------
    // LÓGICA DE FINALIZAÇÃO DE VENDA (Ação 11)
    // ----------------------------------------------------
    
    // 1. Abre o modal de pagamento
    $('#finalize-sale-btn').on('click', function() {
        openPaymentModal();
    });

    // 2. Cálculo de troco ao digitar valor recebido
    $('#payment-received').on('keyup change', function() {
        calculateChange();
    });

    // 3. Confirma e envia os dados finais para o backend
    $('#confirm-payment-btn').on('click', function() {
        finalizeSale();
    });
    
    // ----------------------------------------------------
    // OUTRAS AÇÕES FINAIS (Rascunho)
    // ----------------------------------------------------
    $('#save-draft-btn').on('click', function() {
        // TODO: Implementar endpoint /api/cart/save_draft
        alert('Funcionalidade de Salvar Orçamento (Rascunho) será implementada em breve. Dados atuais: ' + JSON.stringify(cartState));
    });

});

/**
 * =================================================================
 * MANIPULADORES DE EVENTOS
 * =================================================================
 */
$(document).ready(function() {
    renderPDV();

    let clientSearchTimeout;
    let productSearchTimeout;

    // ----------------------------------------------------
    // GERAL: Remoção de Item
    // ----------------------------------------------------
    $(document).on('click', '.remove-item-btn', function() {
        const indexToRemove = $(this).data('index');
        cartState.items.splice(indexToRemove, 1);
        renderPDV();
    });
    
    // ----------------------------------------------------
    // LÓGICA DE BUSCA DE CLIENTE
    // ----------------------------------------------------
    const $clientInput = $('#client-search-input');
    
    // ... (Manipuladores de cliente inalterados) ...
    $clientInput.on('keyup', function() { 
        clearTimeout(clientSearchTimeout);
        const query = $(this).val();
        clientSearchTimeout = setTimeout(() => { searchClients(query); }, 300); 
    });
    $('#client-search-btn').on('click', function() { searchClients($clientInput.val()); });
    $(document).on('click', '.client-select-item', function(e) {
        e.preventDefault();
        const $item = $(this);
        selectClient($item.data('client-id'), $item.data('client-name'), $item.data('client-doc'), $item.data('client-cr'));
    });
    $('#clientSearchModal').on('shown.bs.modal', function () {
        $clientInput.trigger('focus');
        $('#client-search-results-area').empty(); 
    });


    // ----------------------------------------------------
    // LÓGICA DE BUSCA E CONFIGURAÇÃO DE PRODUTOS
    // ----------------------------------------------------
    const $productInput = $('#product-search-input');
    
    // Ação ao digitar (debounce)
    $productInput.on('keyup', function() {
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

    // Ação ao selecionar um produto na busca
    $(document).on('click', '.product-select-item', function(e) {
        e.preventDefault();
        const productData = JSON.parse($(this).data('product'));
        configureItem(productData);
    });
    
    // Ação ao clicar no botão de Adicionar ao Carrinho dentro do modal (CHAMADA API)
    $('#add-to-cart-btn').on('click', function() {
        addItemToCart();
    });

    // Lógica para garantir que o campo de preço aceite apenas números e vírgulas (ajuste cultural)
    $('#config-unit-price').on('change', function() {
        let value = $(this).val().replace(',', '.');
        $(this).val(parseFloat(value).toFixed(2));
    });

    // Ação ao clicar no botão do scanner
    $('#scan-button').on('click', function() {
        $productInput.trigger('focus');
    });
});