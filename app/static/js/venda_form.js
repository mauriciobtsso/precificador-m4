document.addEventListener("DOMContentLoaded", function() {
    
    // --- VARIÁVEIS GLOBAIS ---
    let CARRINHO = [];
    let PRODUTO_ATUAL = null;
    let ESTOQUE_ATUAL = []; // Cache do estoque para validação do scanner
    
    // --- ELEMENTOS DOM (Mapeando o novo HTML) ---
    
    // Cliente
    const areaBuscaCliente = document.getElementById('area_busca_cliente');
    const infoCliente = document.getElementById('info_cliente_selecionado');
    const inpCliente = document.getElementById('busca_cliente');
    const listaClientes = document.getElementById('lista_clientes');
    
    // Produto e Controles
    const inpProduto = document.getElementById('busca_produto');
    const listaProdutos = document.getElementById('lista_produtos');
    const divSerial = document.getElementById('div_serial_wrapper');
    const selSerial = document.getElementById('temp_serial_id');
    const divMunicao = document.getElementById('div_municao_wrapper');
    const inpScan = document.getElementById('scan_lote');
    const hidLoteId = document.getElementById('temp_lote_estoque_id');
    const feedbackLote = document.getElementById('feedback_lote');
    const selCraf = document.getElementById('temp_craf_id');
    const placeholderSelecao = document.getElementById('placeholder_selecao');

    // Carrinho e Totais
    const emptyMsg = document.getElementById('empty_cart_msg');
    const txtSubtotal = document.getElementById('resumo_subtotal');
    const txtTotalFinal = document.getElementById('resumo_total_final');
    const inpDesconto = document.getElementById('venda_desconto');

    // --- 1. LÓGICA DE CLIENTE ---

    inpCliente.addEventListener('input', async (e) => {
        const termo = e.target.value;
        if (termo.length < 3) { listaClientes.style.display = 'none'; return; }

        try {
            const res = await fetch(`/vendas/api/clientes?q=${termo}`);
            const clientes = await res.json();

            listaClientes.innerHTML = '';
            if(clientes.length === 0) {
                listaClientes.innerHTML = '<div class="list-group-item text-muted small">Nenhum cliente encontrado.</div>';
            }

            clientes.forEach(c => {
                const item = document.createElement('a');
                item.className = 'list-group-item list-group-item-action cursor-pointer';
                item.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center">
                        <div><strong>${c.nome}</strong></div>
                        <small class="text-muted">${c.documento}</small>
                    </div>
                `;
                item.onclick = () => selecionarCliente(c);
                listaClientes.appendChild(item);
            });
            listaClientes.style.display = 'block';
        } catch (e) { console.error("Erro busca cliente:", e); }
    });

    function selecionarCliente(c) {
        // Preenche hiddens
        document.getElementById('cliente_id').value = c.id;
        document.getElementById('cliente_doc').value = c.documento;
        document.getElementById('cliente_cr').value = c.cr || '-';

        // Preenche o Card Azul (Visual)
        document.getElementById('txt_cliente_nome').textContent = c.nome;
        document.getElementById('txt_cliente_doc').textContent = c.documento;
        document.getElementById('txt_cliente_cr').textContent = c.cr || 'Sem CR';

        // Troca a visibilidade
        areaBuscaCliente.style.display = 'none';
        infoCliente.style.setProperty('display', 'flex', 'important'); // Force flex do bootstrap
        
        listaClientes.style.display = 'none';
        
        // Se já tinha produto selecionado (Munição), recarrega CRAFs para este novo cliente
        if(PRODUTO_ATUAL && divMunicao.style.display !== 'none') {
            carregarCrafsCliente(PRODUTO_ATUAL.calibre);
        }
    }

    // Função global para o botão "Trocar" no HTML
    window.limparCliente = function() {
        if(CARRINHO.length > 0) {
            if(!confirm("Trocar o cliente pode invalidar os CRAFs vinculados no carrinho. Deseja continuar?")) return;
        }
        
        document.getElementById('cliente_id').value = '';
        infoCliente.style.setProperty('display', 'none', 'important');
        areaBuscaCliente.style.display = 'block';
        inpCliente.value = '';
        setTimeout(() => inpCliente.focus(), 100);
    };

    // --- 2. LÓGICA DE PRODUTO ---

    inpProduto.addEventListener('input', async (e) => {
        const termo = e.target.value;
        if (termo.length < 3) { listaProdutos.style.display = 'none'; return; }

        try {
            const res = await fetch(`/vendas/api/produtos?q=${termo}`);
            const produtos = await res.json();

            listaProdutos.innerHTML = '';
            if(produtos.length === 0) {
                listaProdutos.innerHTML = '<div class="list-group-item text-muted small">Nenhum produto encontrado.</div>';
            }

            produtos.forEach(p => {
                // Badge de Estoque
                let badgeClass = p.estoque > 0 ? 'bg-success' : 'bg-warning text-dark';
                let badgeText = `${p.estoque} un.`;
                
                // Identifica visualmente se é arma
                const nomeLower = p.nome.toLowerCase();
                if(nomeLower.includes('pistola') || nomeLower.includes('fuzil') || nomeLower.includes('revolver')) {
                    badgeText = `<i class="fas fa-shield-alt"></i> ${badgeText}`;
                }

                const item = document.createElement('a');
                item.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center cursor-pointer';
                item.innerHTML = `
                    <div>${p.nome}</div>
                    <span class="badge ${badgeClass}">${badgeText}</span>
                `;
                item.onclick = () => carregarDetalhesProduto(p.id);
                listaProdutos.appendChild(item);
            });
            listaProdutos.style.display = 'block';
        } catch (e) { console.error(e); }
    });

    async function carregarDetalhesProduto(id) {
        listaProdutos.style.display = 'none';
        
        try {
            const res = await fetch(`/vendas/api/produto/${id}/detalhes`);
            PRODUTO_ATUAL = await res.json();

            // Preenche campos básicos
            document.getElementById('temp_produto_id').value = PRODUTO_ATUAL.id;
            document.getElementById('busca_produto').value = PRODUTO_ATUAL.nome;
            document.getElementById('temp_preco').value = PRODUTO_ATUAL.preco.toFixed(2);
            document.getElementById('info_estoque').textContent = `Estoque atual: ${PRODUTO_ATUAL.estoque} unidades.`;

            // --- DECISÃO DE INTERFACE (ENCRUZILHADA) ---
            const tipo = PRODUTO_ATUAL.tipo.toLowerCase();
            const cat = PRODUTO_ATUAL.categoria.toLowerCase();
            const nome = PRODUTO_ATUAL.nome.toLowerCase();

            // Reset Visual
            placeholderSelecao.style.display = 'none';
            divSerial.style.display = 'none';
            divMunicao.style.display = 'none';

            // CASO 1: ARMA (Requer Serial)
            if (tipo.includes('arma') || cat.includes('pistola') || cat.includes('fuzil') || cat.includes('revolver') || cat.includes('espingarda') || cat.includes('carabina')) {
                divSerial.style.display = 'block';
                carregarEstoqueLoja(PRODUTO_ATUAL.id, 'arma');
            }
            // CASO 2: MUNIÇÃO (Requer Lote + CRAF)
            else if (tipo.includes('munição') || nome.includes('munição') || nome.includes('cartucho') || nome.includes('pólvora')) {
                divMunicao.style.display = 'block';
                
                carregarEstoqueLoja(PRODUTO_ATUAL.id, 'municao');
                carregarCrafsCliente(PRODUTO_ATUAL.calibre);
                
                // Foca no scanner
                setTimeout(() => inpScan.focus(), 200);
            } 
            // CASO 3: LIVRE
            else {
                placeholderSelecao.style.display = 'block';
                placeholderSelecao.querySelector('input').value = "Produto Livre (Sem rastreio)";
            }

        } catch(e) { console.error("Erro detalhe produto", e); }
    }

    async function carregarEstoqueLoja(produtoId, tipoContexto) {
        const res = await fetch(`/vendas/api/estoque/${produtoId}`);
        ESTOQUE_ATUAL = await res.json();

        if (tipoContexto === 'arma') {
            selSerial.innerHTML = '<option value="">-- Selecione Serial --</option>';
            if(ESTOQUE_ATUAL.length === 0) {
                 selSerial.innerHTML += '<option value="">Sem estoque físico (Venda Encomenda)</option>';
            }
            ESTOQUE_ATUAL.forEach(i => {
                selSerial.innerHTML += `<option value="${i.id}">${i.serial} ${i.lote ? '(Lote '+i.lote+')' : ''}</option>`;
            });
        } 
        else if (tipoContexto === 'municao') {
            // Prepara scanner
            inpScan.value = "";
            inpScan.classList.remove('is-valid', 'is-invalid');
            hidLoteId.value = "";
            
            if(ESTOQUE_ATUAL.length > 0) {
                feedbackLote.innerHTML = `<span class="text-muted"><i class="fas fa-info-circle"></i> ${ESTOQUE_ATUAL.length} lotes disponíveis. Bipe a caixa.</span>`;
            } else {
                feedbackLote.innerHTML = `<span class="text-warning"><i class="fas fa-exclamation-triangle"></i> Sem estoque físico. Venda será Encomenda.</span>`;
            }
        }
    }

    async function carregarCrafsCliente(calibreExigido) {
        const clienteId = document.getElementById('cliente_id').value;
        
        selCraf.innerHTML = '<option>Carregando...</option>';
        
        if(!clienteId) {
            selCraf.innerHTML = '<option value="">Selecione o cliente primeiro!</option>';
            return;
        }

        try {
            const res = await fetch(`/vendas/api/cliente/${clienteId}/armas?calibre=${encodeURIComponent(calibreExigido)}`);
            const armas = await res.json();
            
            selCraf.innerHTML = '<option value="">Selecione a Arma (CRAF)...</option>';
            
            if(armas.length === 0) {
                const opt = document.createElement('option');
                opt.text = `⚠️ Nenhuma arma ${calibreExigido} encontrada!`;
                opt.disabled = true;
                selCraf.appendChild(opt);
                
                // Injeta botão de cadastro rápido se não existir
                if(!document.getElementById('btnQuickAddArma')) {
                    const btn = document.createElement('button');
                    btn.id = 'btnQuickAddArma';
                    btn.type = 'button';
                    btn.className = 'btn btn-sm btn-outline-danger w-100 mt-1';
                    btn.innerHTML = '<i class="fas fa-plus"></i> Cadastrar Arma Agora';
                    btn.onclick = abrirModalNovaArma;
                    selCraf.parentNode.appendChild(btn);
                }
            } else {
                const btn = document.getElementById('btnQuickAddArma');
                if(btn) btn.remove();

                armas.forEach(a => {
                    selCraf.innerHTML += `<option value="${a.id}">${a.descricao} - ${a.serial} (${a.sistema})</option>`;
                });
            }
        } catch(e) { console.error(e); }
    }

    // --- 3. SCANNER DE LOTE ---
    if(inpScan) {
        inpScan.addEventListener('input', function(e) {
            const codigo = e.target.value.trim();
            if (!codigo) return;

            // Busca inteligente: Por Cod. Barras (embalagem) OU Lote exato
            const loteEncontrado = ESTOQUE_ATUAL.find(i => 
                (i.embalagem && i.embalagem === codigo) || 
                (i.lote && i.lote.toLowerCase() === codigo.toLowerCase())
            );

            if (loteEncontrado) {
                hidLoteId.value = loteEncontrado.id;
                feedbackLote.innerHTML = `<strong class="text-success"><i class="fas fa-check-circle"></i> Lote ${loteEncontrado.lote} Identificado!</strong>`;
                inpScan.classList.add('is-valid');
                inpScan.classList.remove('is-invalid');
                // Opcional: Dar um "bip" sonoro via JS
            } else {
                hidLoteId.value = "";
                feedbackLote.innerHTML = `<span class="text-danger"><i class="fas fa-times-circle"></i> Código não encontrado neste produto.</span>`;
                inpScan.classList.add('is-invalid');
                inpScan.classList.remove('is-valid');
            }
        });
        
        // Evita submit do form ao dar Enter no scanner
        inpScan.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') e.preventDefault(); 
        });
    }

    // --- 4. ADICIONAR AO CARRINHO ---
    document.getElementById('btnAdicionarItem').addEventListener('click', () => {
        if(!PRODUTO_ATUAL) { alert("Selecione um produto primeiro!"); return; }

        const prodId = document.getElementById('temp_produto_id').value;
        const nome = document.getElementById('busca_produto').value;
        const preco = parseFloat(document.getElementById('temp_preco').value || 0);
        const qtdInput = document.getElementById('temp_quantidade');
        const quantidade = parseInt(qtdInput.value > 0 ? qtdInput.value : 1);

        // Captura Contexto
        const serialId = selSerial ? selSerial.value : null;
        const loteId = hidLoteId ? hidLoteId.value : null;
        const crafId = selCraf ? selCraf.value : null;

        // --- VALIDAÇÕES DE REGRA DE NEGÓCIO ---

        // A. Munição
        if (divMunicao.style.display !== 'none') {
            if (!crafId) { 
                alert("⚠️ Bloqueio Legal: Selecione a arma (CRAF) do cliente para vender esta munição.");
                return; 
            }
            // Se quiser obrigar o scanner:
            // if (!loteId) { alert("Bipe o lote da munição!"); return; }
        }

        // B. Arma
        if (divSerial.style.display !== 'none') {
            // Se tem serial selecionado, qtd deve ser 1
            if (serialId && quantidade > 1) {
                alert("⚠️ Armas controladas devem ser adicionadas uma por vez (Serial Único).");
                return;
            }
        }

        // Monta Descrição Rica para a Tabela
        let detalheHtml = "";
        let itemEstoqueId = null;

        // Se achou Lote (Scanner)
        if (loteId) {
            const l = ESTOQUE_ATUAL.find(x => x.id == loteId);
            detalheHtml = `<span class="badge bg-info text-dark"><i class="fas fa-box"></i> Lote: ${l ? l.lote : '?'}</span>`;
            itemEstoqueId = loteId;
        } 
        // Se achou Serial (Dropdown)
        else if (serialId) {
            const s = ESTOQUE_ATUAL.find(x => x.id == serialId);
            detalheHtml = `<span class="badge bg-dark"><i class="fas fa-fingerprint"></i> Serial: ${s ? s.serial : '?'}</span>`;
            itemEstoqueId = serialId;
        } 
        // Se não tem nenhum, é Encomenda ou Livre
        else {
             if(divSerial.style.display !== 'none') detalheHtml = `<span class="badge bg-warning text-dark">Sob Encomenda</span>`;
             else detalheHtml = `<span class="text-muted small">Item de Varejo</span>`;
        }

        // Adiciona CRAF na descrição se tiver
        if (crafId) {
             const crafTexto = selCraf.options[selCraf.selectedIndex].text;
             detalheHtml += `<div class="mt-1 small text-primary"><i class="fas fa-id-card"></i> Ref: ${crafTexto}</div>`;
        }

        CARRINHO.push({
            produto_id: prodId,
            nome: nome,
            preco: preco,
            quantidade: quantidade,
            item_estoque_id: itemEstoqueId,
            arma_cliente_id: crafId || null,
            detalhe_html: detalheHtml
        });

        renderizarCarrinho();
        resetarSelecaoProduto();
    });

    function renderizarCarrinho() {
        const tbody = document.querySelector('#tabelaItens tbody');
        tbody.innerHTML = '';
        let total = 0;

        if(CARRINHO.length === 0) {
            if(emptyMsg) emptyMsg.style.display = 'block';
        } else {
            if(emptyMsg) emptyMsg.style.display = 'none';
            
            CARRINHO.forEach((i, idx) => {
                const subtotal = i.preco * i.quantidade;
                total += subtotal;
                
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="ps-3 fw-bold text-dark">${i.nome}</td>
                    <td>${i.detalhe_html}</td>
                    <td class="text-center">${i.quantidade}</td>
                    <td class="text-end">R$ ${i.preco.toFixed(2)}</td>
                    <td class="text-end fw-bold text-success">R$ ${subtotal.toFixed(2)}</td>
                    <td class="text-end pe-3">
                        <button type="button" class="btn btn-link text-danger p-0" onclick="removerItem(${idx})" title="Remover">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }

        // Atualiza Totais
        const totalFormatado = `R$ ${total.toFixed(2)}`;
        txtSubtotal.innerText = totalFormatado;
        
        // Aplica desconto
        const desc = parseFloat(inpDesconto.value || 0);
        const final = total - desc;
        txtTotalFinal.innerText = `R$ ${final.toFixed(2)}`;
    }

    // Torna a função global para ser chamada pelo onclick do HTML
    window.removerItem = (idx) => {
        CARRINHO.splice(idx, 1);
        renderizarCarrinho();
    };
    
    // Recalcula total se mudar o desconto
    inpDesconto.addEventListener('input', () => renderizarCarrinho());

    function resetarSelecaoProduto() {
        document.getElementById('busca_produto').value = '';
        document.getElementById('temp_produto_id').value = '';
        document.getElementById('temp_quantidade').value = '1';
        document.getElementById('info_estoque').textContent = '';
        
        placeholderSelecao.style.display = 'block';
        divSerial.style.display = 'none';
        divMunicao.style.display = 'none';
        
        PRODUTO_ATUAL = null;
        ESTOQUE_ATUAL = [];
        
        // Limpa scanner
        if(inpScan) {
            inpScan.value = "";
            inpScan.classList.remove('is-valid', 'is-invalid');
            feedbackLote.innerText = "";
            hidLoteId.value = "";
        }
    }

    // --- 5. SUBMIT FINAL ---
    document.getElementById('formVenda').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const clienteId = document.getElementById('cliente_id').value;
        if(!clienteId) { alert("Por favor, identifique o cliente."); return; }
        if(CARRINHO.length === 0) { alert("O carrinho está vazio."); return; }

        const btn = e.target.querySelector('button[type="submit"]');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-circle-notch fa-spin me-2"></i> Processando...';

        try {
            const res = await fetch('/vendas/nova', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    cliente_id: clienteId,
                    itens: CARRINHO,
                    desconto: document.getElementById('venda_desconto').value
                })
            });
            
            const data = await res.json();
            if (data.success) {
                // Redireciona para o Dashboard da Venda
                window.location.href = `/vendas/${data.venda_id}`;
            } else {
                alert("Erro ao salvar: " + data.error);
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        } catch(err) {
            console.error(err);
            alert("Erro de comunicação com o servidor.");
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    });

    // --- MODAL DE CADASTRO RÁPIDO (MANTIDO IGUAL) ---
    window.abrirModalNovaArma = function() {
        if(PRODUTO_ATUAL) {
            document.getElementById('new_arma_calibre').value = PRODUTO_ATUAL.calibre;
        }
        new bootstrap.Modal(document.getElementById('modalNovaArmaCliente')).show();
    };

    document.getElementById('formNovaArmaRapida').addEventListener('submit', async (e) => {
        e.preventDefault();
        const clienteId = document.getElementById('cliente_id').value;
        
        // Pega os dados do form do modal
        const payload = {
            especie: document.getElementById('new_arma_especie').value,
            marca: document.getElementById('new_arma_marca').value,
            modelo: document.getElementById('new_arma_modelo').value,
            calibre: document.getElementById('new_arma_calibre').value,
            numero_serie: document.getElementById('new_arma_serial').value,
            registro: document.getElementById('new_arma_registro').value
        };

        try {
            const res = await fetch(`/clientes/api/${clienteId}/armas/novo`, { // ATENÇÃO: Verifique se essa rota existe
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });

            if(res.ok) {
                bootstrap.Modal.getInstance(document.getElementById('modalNovaArmaCliente')).hide();
                alert("Arma cadastrada com sucesso!");
                // Recarrega a lista de CRAFs para aparecer a nova arma
                if(PRODUTO_ATUAL) carregarCrafsCliente(PRODUTO_ATUAL.calibre);
            } else {
                alert("Erro ao salvar arma.");
            }
        } catch(e) { console.error(e); alert("Erro ao salvar."); }
    });

});