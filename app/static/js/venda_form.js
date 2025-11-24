document.addEventListener("DOMContentLoaded", function() {
    
    let CARRINHO = [];
    
    // Referências de DOM globais para facilitar
    const selSerial = document.getElementById('temp_serial_id');
    const divSerial = document.getElementById('div_serial_wrapper');
    const selCraf = document.getElementById('temp_craf_id');
    const divCraf = document.getElementById('div_craf_wrapper');

    // --- 1. BUSCA DE CLIENTES ---
    const inpCliente = document.getElementById('busca_cliente');
    const listaClientes = document.getElementById('lista_clientes');

    inpCliente.addEventListener('input', async (e) => {
        const termo = e.target.value;
        if (termo.length < 3) { listaClientes.style.display = 'none'; return; }

        try {
            const res = await fetch(`/vendas/api/clientes?q=${termo}`);
            const clientes = await res.json();

            listaClientes.innerHTML = '';
            clientes.forEach(c => {
                const item = document.createElement('a');
                item.className = 'list-group-item list-group-item-action';
                item.innerHTML = `<strong>${c.nome}</strong> <small class='text-muted'>(${c.documento})</small>`;
                item.onclick = () => selecionarCliente(c);
                listaClientes.appendChild(item);
            });
            listaClientes.style.display = 'block';
        } catch (e) { console.error("Erro ao buscar clientes", e); }
    });

    function selecionarCliente(c) {
        document.getElementById('cliente_id').value = c.id;
        document.getElementById('busca_cliente').value = c.nome;
        document.getElementById('cliente_doc').value = c.documento;
        document.getElementById('cliente_cr').value = c.cr || '-'; 
        listaClientes.style.display = 'none';
        
        // Se trocou de cliente, limpa o CRAF selecionado se houver munição pendente na tela
        if(selCraf) selCraf.innerHTML = '<option value="">Selecione o produto...</option>';
    }

    // --- 2. BUSCA DE PRODUTOS ---
    const inpProduto = document.getElementById('busca_produto');
    const listaProdutos = document.getElementById('lista_produtos');

    inpProduto.addEventListener('input', async (e) => {
        const termo = e.target.value;
        if (termo.length < 3) { listaProdutos.style.display = 'none'; return; }

        try {
            const res = await fetch(`/vendas/api/produtos?q=${termo}`);
            const produtos = await res.json();

            listaProdutos.innerHTML = '';
            produtos.forEach(p => {
                // Detecta visualmente se é arma ou munição
                let badge = `<span class="badge bg-${p.estoque > 0 ? 'success' : 'warning'}">${p.estoque} un.</span>`;
                if (p.nome.toLowerCase().includes('pistola') || p.nome.toLowerCase().includes('fuzil')) {
                    badge = `<span class="badge bg-dark">ARMA</span> ` + badge;
                }

                const item = document.createElement('a');
                item.className = 'list-group-item list-group-item-action d-flex justify-content-between';
                item.innerHTML = `<div>${p.nome}</div> <div>${badge}</div>`;
                item.onclick = () => selecionarProduto(p);
                listaProdutos.appendChild(item);
            });
            listaProdutos.style.display = 'block';
        } catch (e) { console.error("Erro ao buscar produtos", e); }
    });

    async function selecionarProduto(p) {
        document.getElementById('temp_produto_id').value = p.id;
        document.getElementById('busca_produto').value = p.nome;
        document.getElementById('temp_preco').value = p.preco;
        listaProdutos.style.display = 'none';

        // RESET: Esconde todos os seletores especiais inicialmente
        if(divSerial) { divSerial.style.display = 'none'; selSerial.value = ""; }
        if(divCraf) { divCraf.style.display = 'none'; selCraf.value = ""; }

        const nomeLower = p.nome.toLowerCase();
        
        // --- CASO A: É UMA ARMA? (Busca Serial no Estoque) ---
        // Ajuste essa lógica conforme a 'categoria' que vier da API
        if (nomeLower.includes('pistola') || nomeLower.includes('fuzil') || nomeLower.includes('revolver') || nomeLower.includes('carabina') || nomeLower.includes('espingarda')) {
            
            if(divSerial) divSerial.style.display = 'block';
            
            selSerial.innerHTML = '<option value="">Carregando estoque...</option>';
            const res = await fetch(`/vendas/api/estoque/${p.id}`);
            const estoque = await res.json();

            selSerial.innerHTML = '<option value="">-- Selecione (Opcional) --</option>';
            if (estoque.length > 0) {
                estoque.forEach(item => {
                    const opt = document.createElement('option');
                    opt.value = item.id; 
                    opt.text = `Serial: ${item.serial} (Lote: ${item.lote || '-'})`;
                    selSerial.appendChild(opt);
                });
            } else {
                const opt = document.createElement('option');
                opt.value = "";
                opt.text = "Sem estoque físico (Encomenda)";
                selSerial.appendChild(opt);
            }

        // --- CASO B: É MUNIÇÃO? (Busca CRAF do Cliente) ---
        } else if (nomeLower.includes('munição') || nomeLower.includes('cartucho') || nomeLower.includes('pólvora')) {
            
            const clienteId = document.getElementById('cliente_id').value;
            if (!clienteId) {
                alert("⚠️ Atenção: Para vender munição, selecione o CLIENTE primeiro!");
                // Não impedimos, mas o dropdown ficará vazio
            }

            if(divCraf) {
                divCraf.style.display = 'block';
                selCraf.innerHTML = '<option value="">Carregando armas do cliente...</option>';
                
                if (clienteId) {
                    // Busca armas do cliente (você precisará criar essa rota em routes.py ou api.py)
                    // Ex: /clientes/api/123/armas
                    try {
                        const res = await fetch(`/clientes/api/${clienteId}/armas`); 
                        const armas = await res.json();
                        
                        selCraf.innerHTML = '<option value="">Selecione a Arma (CRAF)...</option>';
                        armas.forEach(a => {
                            const opt = document.createElement('option');
                            opt.value = a.id;
                            opt.text = `${a.descricao || a.modelo} - ${a.numero_serie}`;
                            selCraf.appendChild(opt);
                        });
                    } catch(e) {
                        selCraf.innerHTML = '<option value="">Erro ao carregar CRAFs</option>';
                    }
                } else {
                    selCraf.innerHTML = '<option value="">Selecione o cliente primeiro</option>';
                }
            }
        }
    }

    // --- 3. ADICIONAR AO CARRINHO ---
    document.getElementById('btnAdicionarItem').addEventListener('click', () => {
        const prodId = document.getElementById('temp_produto_id').value;
        const nome = document.getElementById('busca_produto').value;
        const preco = parseFloat(document.getElementById('temp_preco').value || 0);
        
        // Captura valores especiais
        const serialId = selSerial ? selSerial.value : null;
        const serialTexto = selSerial && selSerial.selectedIndex >= 0 ? selSerial.options[selSerial.selectedIndex].text : "";
        
        const crafId = selCraf ? selCraf.value : null;
        const crafTexto = selCraf && selCraf.selectedIndex >= 0 ? selCraf.options[selCraf.selectedIndex].text : "";

        if (!prodId) { alert("Selecione um produto!"); return; }

        // Validação simples de Munição
        if (divCraf && divCraf.style.display !== 'none' && !crafId) {
            if(!confirm("Você está vendendo munição sem vincular um CRAF. Deseja continuar mesmo assim?")) {
                return;
            }
        }

        // Monta detalhe visual
        let detalhe = "-";
        if (serialId) detalhe = `<strong>Estoque:</strong> ${serialTexto}`;
        else if (divSerial && divSerial.style.display !== 'none') detalhe = "<em>Sob Encomenda</em>";
        
        if (crafId) detalhe = `<strong>CRAF Vinc:</strong> ${crafTexto}`;

        CARRINHO.push({
            produto_id: prodId,
            nome: nome,
            preco: preco,
            item_estoque_id: serialId || null, // Para Armas
            arma_cliente_id: crafId || null,    // Para Munições
            detalhe_visual: detalhe
        });

        renderizarCarrinho();
        
        // Limpa campos
        document.getElementById('busca_produto').value = '';
        document.getElementById('temp_produto_id').value = '';
        if(selSerial) selSerial.innerHTML = '';
        if(divSerial) divSerial.style.display = 'none';
        if(selCraf) selCraf.value = '';
        if(divCraf) divCraf.style.display = 'none';
    });

    function renderizarCarrinho() {
        const tbody = document.querySelector('#tabelaItens tbody');
        tbody.innerHTML = '';
        let total = 0;

        CARRINHO.forEach((item, idx) => {
            total += item.preco;
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${item.nome}</td>
                <td><small class="text-muted">${item.detalhe_visual}</small></td>
                <td class="text-center">1</td>
                <td class="text-end">R$ ${item.preco.toFixed(2)}</td>
                <td class="text-end">R$ ${item.preco.toFixed(2)}</td>
                <td><button type="button" class="btn btn-sm btn-danger" onclick="removerItem(${idx})"><i class="fas fa-trash"></i></button></td>
            `;
            tbody.appendChild(tr);
        });

        document.getElementById('resumo_subtotal').innerText = `R$ ${total.toFixed(2)}`;
        calcularTotalFinal(total);
    }

    window.removerItem = (idx) => {
        CARRINHO.splice(idx, 1);
        renderizarCarrinho();
    };

    // --- 4. SALVAR (Enviar JSON) ---
    document.getElementById('formVenda').addEventListener('submit', async (e) => {
        e.preventDefault();
        const clienteId = document.getElementById('cliente_id').value;
        if(!clienteId) { alert("Selecione um cliente!"); return; }
        if(CARRINHO.length === 0) { alert("Carrinho vazio!"); return; }

        const payload = {
            cliente_id: clienteId,
            desconto: document.getElementById('venda_desconto').value,
            itens: CARRINHO
        };

        try {
            const btn = e.target.querySelector('button[type="submit"]');
            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processando...';

            const res = await fetch('/vendas/nova', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            
            const data = await res.json();
            if (data.success) {
                window.location.href = `/vendas/${data.venda_id}`; 
            } else {
                alert("Erro: " + data.error);
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        } catch(err) {
            alert("Erro ao salvar venda.");
            console.error(err);
        }
    });

    function calcularTotalFinal(subtotal) {
        const desc = parseFloat(document.getElementById('venda_desconto').value || 0);
        const final = subtotal - desc;
        document.getElementById('resumo_total_final').innerText = `R$ ${final.toFixed(2)}`;
    }
});