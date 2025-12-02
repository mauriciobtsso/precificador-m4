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

// Função para exibir feedback (Usado no modal de configuração de item)
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
        newSubtotal += item.total_item || (item.quantity * item.unit_price);
    });

    cartState.subtotal = newSubtotal;
    // O desconto é subtraído do subtotal
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
            let actionsHtml = ''; // Conteúdo da coluna Ações

            if (item.is_controlled) {
                // Se for controlado, o status depende da configuração (Serial/Lote/CRAF)
                const isConfigured = item.serial || item.lote || item.arma_cliente_id;
                const iconClass = isConfigured ? 'bi-check-circle-fill text-success' : 'bi-lock-fill text-danger';
                statusIcon = `<i class="bi ${iconClass} me-1" title="${isConfigured ? 'Item Configurado' : 'Requer Configuração'}"></i>`;
                
                // Botão para reabrir o modal de configuração
                actionsHtml = `
                    <button class="btn btn-sm btn-warning configure-item-btn" data-index="${index}" title="Configurar Lote/CRAF">
                        <i class="fas fa-cog me-1"></i> Configurar
                    </button>
                `;
            } else {
                // Item não controlado, apenas a lixeira
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
        const stockStatusText = product.estoque_disponivel > 0 ? `${product.estoque_disponivel} em estoque` : `SEM ESTOQUE`;

        const controlledIcon = product.is_controlled ? 
            `<i class="bi bi-lock-fill text-danger me-1" title="Item Controlado"></i>` : '';

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

// NOVA FUNÇÃO: Busca as armas do cliente
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

// FUNÇÃO MODIFICADA: Agora aceita um item (novo ou existente para edição)
async function configureItem(product, itemIndexToEdit = null) {
    
    let currentItem = itemIndexToEdit !== null ? cartState.items[itemIndexToEdit] : product;

    if (!currentItem) return; 

    cartState.tempItem = {
        product_id: currentItem.product_id || currentItem.id,
        product_name: currentItem.product_name || currentItem.nome,
        // Garante que 'unit_price' seja um float antes de armazenar
        unit_price: parseFloat(currentItem.unit_price) || parseFloat(currentItem.preco_venda), 
        quantity: currentItem.quantity || 1, 
        is_controlled: currentItem.is_controlled,
        estoque_disponivel: currentItem.estoque_disponivel,
        // Mantém valores de controle existentes
        serial: currentItem.serial || '',
        lote: currentItem.lote || '',
        craf: currentItem.craf || '',
        arma_cliente_id: currentItem.arma_cliente_id || null, 
        _index: itemIndexToEdit,
        calibre: currentItem.calibre || null 
    };
    
    $('#product-search-results').hide().empty();
    $('#product-search-input').val('');
    
    // 3. Preenche os campos do Modal
    $('#itemConfigModalLabel').text(`Configurar Item - ${cartState.tempItem.product_name}`);
    $('#item-config-name').text(cartState.tempItem.product_name);
    $('#config-quantity').val(cartState.tempItem.quantity);
    
    // 🚨 CORREÇÃO DE FORMATO: Preenche o input formatando float para string com vírgula (Ex: 10,33).
    const formattedPrice = cartState.tempItem.unit_price.toFixed(2).replace('.', ',');
    $('#config-unit-price').val(formattedPrice); 
    
    // 4. Limpa feedbacks anteriores
    $('#config-validation-feedback').empty();

    // 5. Atualiza o status de estoque
    const $stockStatus = $('#config-stock-status');
    const stock = cartState.tempItem.estoque_disponivel;
    $stockStatus.text(`Estoque: ${stock}`);
    $stockStatus.removeClass().addClass(`badge ${stock > 0 ? 'bg-success' : 'bg-danger'}`);
    
    // 6. Mostra/Esconde e preenche campos controlados
    if (cartState.tempItem.is_controlled) {
        $('#controlled-fields-area').show();
        $('#config-serial-lote').val(cartState.tempItem.serial || cartState.tempItem.lote);
        $('#config-craf').val(cartState.tempItem.craf); 
        
        // Lógica para carregar Armas para CRAF/Munição
        if (cartState.clientId && cartState.tempItem.calibre) { 
            const armas = await searchClientArmas(cartState.clientId, cartState.tempItem.calibre);
            // TODO: Aqui você implementaria a renderização do <select> das armas
            console.log("Armas encontradas:", armas);
        } else if (cartState.tempItem.is_controlled) {
             showFeedback('Item controlado. Para CRAF, selecione um cliente e o produto deve ter calibre definido.', 'info');
        }
    } else {
        $('#controlled-fields-area').hide();
    }
    
    // 7. Abre o modal
    const itemConfigModal = new bootstrap.Modal(document.getElementById('itemConfigModal'));
    itemConfigModal.show();
}

async function addItemToCart() {
    const tempItem = cartState.tempItem;
    
    const quantity = parseInt($('#config-quantity').val());
    const rawPriceInput = $('#config-unit-price').val();
    // 🚨 CORREÇÃO CRÍTICA: Sempre substitui vírgula por ponto ANTES de chamar parseFloat
    const price = parseFloat(rawPriceInput.replace(',', '.')); 
    
    const serialLote = $('#config-serial-lote').val().trim();
    const craf = $('#config-craf').val().trim();
    
    // TODO: Capturar armaClienteId do <select> de armas
    const armaClienteId = null; 
    
    if (!cartState.clientId) {
        showFeedback('Selecione um cliente antes de adicionar produtos.', 'warning');
        return;
    }
    if (isNaN(quantity) || quantity <= 0) {
        showFeedback('A quantidade deve ser um número positivo.', 'danger');
        return;
    }
    // A validação agora é precisa, pois 'price' já é um float (ou NaN)
    if (isNaN(price) || price <= 0) {
        showFeedback('O preço unitário deve ser um valor positivo.', 'danger');
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
            if (tempItem._index !== null) {
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
    const received = parseFloat($('#payment-received').val().replace(',', '.')) || 0;
    const change = received - total;

    $('#payment-change').text(`R$ ${change.toFixed(2).replace('.', ',')}`);
    
    if (change >= 0) {
        $('#confirm-payment-btn').prop('disabled', false).removeClass('btn-secondary').addClass('btn-success');
    } else {
        $('#confirm-payment-btn').prop('disabled', true).removeClass('btn-success').addClass('btn-secondary');
    }
}

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
$(document).ready(function() {
    renderPDV();

    let clientSearchTimeout;
    let productSearchTimeout;

    // ----------------------------------------------------
    // GERAL: Remoção e EDIÇÃO de Item
    // ----------------------------------------------------
    $(document).on('click', '.remove-item-btn', function() {
        const indexToRemove = $(this).data('index');
        cartState.items.splice(indexToRemove, 1);
        renderPDV();
    });

    // Ação para reabrir o modal de configuração de itens controlados
    $(document).on('click', '.configure-item-btn', function() {
        const indexToEdit = $(this).data('index');
        const itemToEdit = cartState.items[indexToEdit];
        
        // Passa o item e o índice para a função de configuração para pré-preenchimento
        configureItem(itemToEdit, indexToEdit); 
    });
    
    // ----------------------------------------------------
    // LÓGICA DE BUSCA DE CLIENTE
    // ----------------------------------------------------
    const $clientInput = $('#client-search-input');
    
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
        
        const rawProductJson = $(this).attr('data-product'); 
        
        try {
            const productData = JSON.parse(rawProductJson);
            
            // Inicia o processo de configuração do item no modal (novo item)
            configureItem(productData); 
            
            $('#product-search-input').val(''); 
            
        } catch (error) {
            console.error("Erro ao fazer parse do JSON do produto:", error);
            console.log("JSON Bruto:", rawProductJson);
            alert("Erro interno: Falha ao carregar detalhes do produto. (Verifique se há aspas no nome do produto)");
        }
    });
    
    // Ação ao clicar no botão de Adicionar ao Carrinho dentro do modal
    $('#add-to-cart-btn').on('click', function() {
        addItemToCart();
    });

    // Lógica para garantir que o campo de preço aceite números e formate corretamente
    $('#config-unit-price').on('change', function() {
        let value = $(this).val().replace(',', '.');
        if (!isNaN(parseFloat(value))) {
             $(this).val(parseFloat(value).toFixed(2).replace('.', ','));
        }
    });

    // Ação ao clicar no botão do scanner
    $('#scan-button').on('click', function() {
        $productInput.trigger('focus');
    });
    
    // ----------------------------------------------------
    // LÓGICA DE FINALIZAÇÃO DE VENDA
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
    
    // 4. Placeholder para Salvar Rascunho
    $('#save-draft-btn').on('click', function() {
        alert('Funcionalidade de Salvar Orçamento (Rascunho) será implementada em breve.');
    });
});