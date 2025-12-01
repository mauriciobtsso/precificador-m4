// ===========================================================
// MÓDULO: PRODUTOS_FORM.JS — Com Suporte a Promoção (Versão Corrigida - Módulo)
// ===========================================================

(() => {
  console.log("[M4] produtos_form.js carregado (v-promo)");

  const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  const el = (id) => document.getElementById(id);
  
  // Variáveis globais dentro do módulo para as instâncias do AutoNumeric
  let anFornecedor, anLucroAlvo, anPrecoFinal, anFrete, anIPI, anPromoPreco;
  
  // Helper: Lê número "limpo" de inputs (remove pontos e virgulas)
  const num = (id) => {
      const elem = el(id);
      if (!elem) return 0;
      let val = elem.value.replace(/\./g, "").replace(",", ".");
      val = val.replace("%", "").replace("R$", "").trim();
      return parseFloat(val) || 0;
  };

  // Helper: Lê valor seguro do AutoNumeric
  const getAN = (an) => {
      if (!an) return 0;
      try { return an.getNumber() || 0; } catch (e) { return 0; }
  };

  function getProdutoId() {
    const container = document.querySelector('.container[data-produto-id]');
    const raw = container?.getAttribute('data-produto-id') || "";
    const id = parseInt(raw, 10);
    return Number.isFinite(id) && id > 0 ? id : null;
  }

  // ============================================================
  // FOTO: Lógica para seleção, preview e upload (CORREÇÃO DA PERSISTÊNCIA)
  // ============================================================
  
  // Função que faz o upload via API Flask (que por sua vez usa o R2)
  async function uploadFoto(file, fotoProdutoOverlay, inputFotoUrl, btnRemoverFoto, fotoProdutoPreview, defaultPlaceholder, inputFotoProduto) {
    const produtoId = getProdutoId() || 'novo';
    const formData = new FormData();
    formData.append('file', file);
    formData.append('produto_id', produtoId); // Para o servidor organizar o R2

    if (fotoProdutoOverlay) fotoProdutoOverlay.classList.remove("d-none"); // Mostra o spinner

    try {
      // Endpoint que deve estar implementado no Flask (ex: app/produtos/routes/fotos.py)
      const response = await fetch('/produtos/api/upload_foto', { 
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`Erro no servidor: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      
      if (data.success && data.foto_url) {
        inputFotoUrl.value = data.foto_url; // <--- CHAVE PARA A PERSISTÊNCIA: Atualiza o campo que será enviado ao salvar.
        console.log(`[M4] Foto carregada e URL atualizada: ${data.foto_url}`);
        if (btnRemoverFoto) btnRemoverFoto.classList.remove("d-none");
        
      } else {
        throw new Error(data.message || "Falha ao receber a URL da foto. Tente novamente.");
      }

    } catch (error) {
      console.error("[M4] Erro no upload da foto:", error);
      // Reverte o preview para o placeholder e limpa os campos em caso de falha no upload
      fotoProdutoPreview.src = defaultPlaceholder;
      if(inputFotoUrl) inputFotoUrl.value = "";
      if(inputFotoProduto) inputFotoProduto.value = null;
      alert("Falha ao enviar a foto. Por favor, tente novamente.");

    } finally {
      if (fotoProdutoOverlay) fotoProdutoOverlay.classList.add("d-none"); // Esconde o spinner
    }
  }

  function initFotoProduto() {
      const btnSelecionarFoto = el("btnSelecionarFoto");
      const inputFotoProduto = el("inputFotoProduto");
      const btnRemoverFoto = el("btnRemoverFoto");
      const fotoProdutoPreview = el("fotoProdutoPreview");
      const inputFotoUrl = el("inputFotoUrl");
      const fotoProdutoOverlay = el("fotoProdutoOverlay");

      // Se os elementos chave não existirem, encerra a função
      if (!btnSelecionarFoto || !inputFotoProduto || !fotoProdutoPreview) return;
      
      const defaultPlaceholder = fotoProdutoPreview.src;

      const container = document.getElementById("fotoProdutoContainer");
      if (container && container.dataset.bound === "1") return;
      if (container) container.dataset.bound = "1";

      // 1. Lógica para selecionar o arquivo: Clica no input file escondido
      btnSelecionarFoto.addEventListener("click", (e) => {
        e.preventDefault();
        inputFotoProduto.click();
      });

      // 2. Lógica para preview da imagem e iniciar upload
      inputFotoProduto.addEventListener("change", (event) => {
        const file = event.target.files[0];
        if (file) {
          // Preview imediato (sem persistência)
          const reader = new FileReader();
          reader.onload = (e) => {
            fotoProdutoPreview.src = e.target.result;
          };
          reader.readAsDataURL(file);

          // Inicia o upload assíncrono para o R2/Proxy e salva a URL final
          uploadFoto(file, fotoProdutoOverlay, inputFotoUrl, btnRemoverFoto, fotoProdutoPreview, defaultPlaceholder, inputFotoProduto);
          
        } else {
          // Arquivo deselecionado (cancelado)
          if(inputFotoUrl.value === "") { // Só limpa o preview se não houver URL persistida
              fotoProdutoPreview.src = defaultPlaceholder;
              if (btnRemoverFoto) btnRemoverFoto.classList.add("d-none");
          }
        }
      });
      
      // 3. Lógica do botão remover
      if (btnRemoverFoto) {
        btnRemoverFoto.addEventListener("click", () => {
          fotoProdutoPreview.src = defaultPlaceholder;
          if(inputFotoUrl) inputFotoUrl.value = ""; // Limpa a URL para persistência
          btnRemoverFoto.classList.add("d-none");
          inputFotoProduto.value = null; // Limpa o input file
          // NOTA: Para remover a foto do R2, uma chamada adicional ao backend seria necessária aqui.
        });
      }
      console.info("[M4] Inicialização da Foto OK. ✅");
  }


  // ============================================================
  // Máscara dinâmica do IPI (Manutenção da Lógica)
  // ============================================================
  const ipiInput = document.getElementById("in_ipi");
  const ipiTipoSelect = document.getElementById("in_ipi_tipo");

  function initIpiMask(forceClear = false) {
    if (!ipiInput || !ipiTipoSelect) return;

    let valorAtual = 0;
    if (anIPI && AutoNumeric.isManagedByAutoNumeric(ipiInput)) {
        valorAtual = anIPI.getNumber();
    } else {
        valorAtual = num("in_ipi");
    }
    if (forceClear) valorAtual = 0;

    if (anIPI && AutoNumeric.isManagedByAutoNumeric(ipiInput)) {
        anIPI.remove();
    }

    const tipoNovo = ipiTipoSelect.value;
    const ipiOpts = {
        digitGroupSeparator: ".",
        decimalCharacter: ",",
        decimalPlaces: 2,
        modifyValueOnWheel: false,
        emptyInputBehavior: "zero",
        unformatOnSubmit: true
    };

    if (tipoNovo === "fixo" || tipoNovo === "R$") {
      anIPI = new AutoNumeric(ipiInput, { ...ipiOpts, currencySymbol: "R$ " });
    } else {
      anIPI = new AutoNumeric(ipiInput, { ...ipiOpts, suffixText: " %", maximumValue: "1000", minimumValue: "0" });
    }

    anIPI.set(valorAtual);
    ipiInput.dataset.maskType = tipoNovo;
  }
  
  // Listener para IPI Tipo
  if (ipiTipoSelect) {
      ipiTipoSelect.addEventListener("change", () => {
        initIpiMask(true); 
        recalcular();
      });
  }

  // ============================================================
  // INICIALIZAÇÃO DE MÁSCARAS (Função unificada para init e reinit)
  // ============================================================
  function initMasks() {
    if (typeof AutoNumeric === "undefined") {
      console.warn("[M4] AutoNumeric não encontrado. Máscaras desativadas.");
      return;
    }
    
    // Remove instâncias AutoNumeric existentes antes de recriar
    const elementsToRemove = document.querySelectorAll('.autonumeric-managed');
    elementsToRemove.forEach(el => {
        if (AutoNumeric.isManagedByAutoNumeric(el)) {
            try { AutoNumeric.getAutoNumericElement(el).remove(); } catch (e) { /* silent fail */ }
        }
    });

    const baseOpts = {
      digitGroupSeparator: ".",
      decimalCharacter: ",",
      decimalPlaces: 2,
      currencySymbolPlacement: "p",
      unformatOnSubmit: true,
      emptyInputBehavior: "zero",
      modifyValueOnWheel: false,
    };
    const brlOpts = { ...baseOpts, currencySymbol: "R$ " };
    const percOpts = { ...baseOpts, suffixText: " %", currencySymbol: "" };

    // Helper Factory
    const createMoney = (selector) => {
      const element = document.querySelector(selector);
      if (!element) return null;
      element.classList.add('autonumeric-managed');
      const an = new AutoNumeric(selector, brlOpts);
      if (element.value && element.value.trim() !== "") {
          an.set(element.value);
      }
      return an;
    };

    // Inicializa campos principais (Restaurando IDs originais)
    anFornecedor = createMoney("#in_preco_fornecedor");
    anLucroAlvo  = createMoney("#in_lucro_alvo");
    anPrecoFinal = createMoney("#in_preco_final");
    anFrete      = createMoney("#in_frete");
    anPromoPreco = createMoney("#in_promo_preco");

    // Campos percentuais simples
    ["in_margem", "in_difal", "in_imposto_venda", "in_desconto"].forEach((id) => {
      const selector = `#${id}`;
      const $i = el(id);
      if ($i) {
        try { 
            $i.setAttribute("type", "text"); 
            $i.classList.add('autonumeric-managed');
            new AutoNumeric(selector, percOpts);
        } catch (_) {} 
      }
    });

    // Inicializa IPI (Dinâmico)
    initIpiMask(false);
    
    // Listeners para AutoNumeric
    document.removeEventListener("autoNumeric:rawValueModified", recalcularListener);
    document.addEventListener("autoNumeric:rawValueModified", recalcularListener);
  }

  // Listener principal do AutoNumeric, para evitar duplicação de eventos
  function recalcularListener(e) {
    if (["in_preco_fornecedor", "in_lucro_alvo", "in_preco_final", "in_frete", "in_ipi", "in_promo_preco"].includes(e.target.id)) {
      recalcular();
    }
  }


  // =========================================
  // LÓGICA FINANCEIRA (Com Promoção)
  // =========================================
  function recalcular() {
    try {
      // 1. Determina Preço Base (Promoção vs Normal)
      let precoBase = getAN(anFornecedor);
      
      const promoAtiva = el("in_promo_ativada")?.checked;
      const promoPreco = getAN(anPromoPreco);
      const dataInicio = el("in_promo_inicio")?.value;
      const dataFim = el("in_promo_fim")?.value;

      let usandoPromo = false;
      if (promoAtiva && promoPreco > 0) {
          const agora = new Date();
          const dtIni = dataInicio ? new Date(dataInicio) : null;
          const dtFim = dataFim ? new Date(dataFim) : null;
          
          if ((!dtIni || agora >= dtIni) && (!dtFim || agora <= dtFim)) {
              precoBase = promoPreco;
              usandoPromo = true;
          }
      }

      // Feedback visual no campo de fornecedor
      const lblFornecedor = el("in_preco_fornecedor");
      const promoPrecoEl = el("in_promo_preco");
      if(lblFornecedor) {
          if(usandoPromo) {
              lblFornecedor.classList.add("text-decoration-line-through", "text-muted");
              if(promoPrecoEl) promoPrecoEl.classList.add("border-success", "text-success", "fw-bold");
          } else {
              lblFornecedor.classList.remove("text-decoration-line-through", "text-muted");
              if(promoPrecoEl) promoPrecoEl.classList.remove("border-success", "text-success", "fw-bold");
          }
      }

      // 2. Lê outros valores
      const frete = getAN(anFrete);
      const descFornecedor = num("in_desconto");
      const margem = num("in_margem");
      const impostoVenda = num("in_imposto_venda");
      const difal = num("in_difal");
      const lucroAlvo = getAN(anLucroAlvo);
      
      const ipiTipo = el("in_ipi_tipo")?.value || "%_dentro";
      let ipiValor = (anIPI && AutoNumeric.isManagedByAutoNumeric(el("in_ipi"))) 
                     ? anIPI.getNumber() : num("in_ipi");

      let precoFinal = getAN(anPrecoFinal);

      // 3. Cálculos
      const valorComDesconto = precoBase * (1 - descFornecedor / 100);
      
      if (el("out_desconto")) el("out_desconto").textContent = brl.format(valorComDesconto || 0);
      if (el("out_frete")) el("out_frete").textContent = brl.format(frete || 0);

      const base = valorComDesconto;

      // IPI
      let valorIPI = 0;
      if (ipiTipo === "%_dentro") {
        const baseSemIPI = base / (1 + ipiValor / 100);
        valorIPI = base - baseSemIPI;
      } else if (ipiTipo === "%") {
        valorIPI = base * (ipiValor / 100);
      } else {
        valorIPI = ipiValor;
      }

      // DIFAL
      const baseDifal = Math.max(base - valorIPI + frete, 0);
      const valorDifal = baseDifal * (difal / 100);
      
      // Custo Total
      const custoTotal = base + valorDifal + frete;

      // Sugestão de Preço
      if (!(precoFinal > 0)) {
        if (lucroAlvo > 0) {
          precoFinal = (custoTotal + lucroAlvo) / (1 - impostoVenda / 100);
        } else if (margem > 0) {
          precoFinal = custoTotal / (1 - margem / 100);
        } else {
          precoFinal = custoTotal;
        }
      }

      // Resultados Finais
      const impostoVendaValor = precoFinal * (impostoVenda / 100);
      const lucroLiquido = precoFinal - custoTotal - impostoVendaValor;

      // 4. Exibe na Tela (Resumo)
      const setVal = (id, val) => { const elem = el(id); if (elem) elem.value = brl.format(isFinite(val) ? val : 0); };
      setVal("out_custo_total", custoTotal);
      setVal("out_preco_a_vista", precoFinal);
      setVal("out_lucro_liquido", lucroLiquido);

      if (el("out_ipi")) el("out_ipi").textContent = brl.format(valorIPI || 0);
      if (el("out_difal")) el("out_difal").textContent = brl.format(valorDifal || 0);
      if (el("out_imposto")) el("out_imposto").textContent = brl.format(impostoVendaValor || 0);

      atualizarResumoVisual(lucroLiquido);

    } catch (err) {
      console.error("[M4] Erro no cálculo:", err);
    }
  }

  function atualizarResumoVisual(lucroLiquido) {
    const lucroEl = el("out_lucro_liquido");
    if (!lucroEl) return;
    if (lucroLiquido > 0.009) {
        lucroEl.style.color = "#198754"; 
        lucroEl.style.fontWeight = "600";
    } else if (lucroLiquido < -0.009) {
        lucroEl.style.color = "#dc3545";
        lucroEl.style.fontWeight = "600";
    } else {
        lucroEl.style.color = "#6c757d";
        lucroEl.style.fontWeight = "normal";
    }
  }

  // =========================================
  // Listeners para campos não-AutoNumeric
  // =========================================
  const debounce = (fn, delay = 200) => {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); };
  };

  function setupStaticListeners() {
    // Inputs que disparam recalculo (além dos de AutoNumeric)
    const idsTriggers = [
        "in_desconto", "in_margem", "in_imposto_venda", "in_difal", "in_ipi", 
        "in_promo_ativada", "in_promo_inicio", "in_promo_fim" 
    ];

    idsTriggers.forEach((id) => {
      const input = el(id);
      if (input) input.addEventListener("input", debounce(recalcular, 300));
      if (input && input.type === 'checkbox') input.addEventListener("change", recalcular);
    });
  }

  function corrigirAlturaAbas() {
    const tabs = document.querySelectorAll("#produtoTabs .nav-link");
    tabs.forEach(t => t.style.minWidth = "100px");
  }

  // =========================================
  // EXPORTAÇÃO DO MÓDULO (Para atender a produto_form.html)
  // =========================================
  const ProdutosForm = {
    // Método principal chamado em window.load
    init: function() {
      // 1. Inicializa a lógica de foto (CORREÇÃO)
      initFotoProduto(); 

      // 2. Inicializa as máscaras e listeners do AutoNumeric
      initMasks(); 

      // 3. Configura listeners para campos estáticos
      setupStaticListeners();
      
      // 4. Corrige altura das abas
      corrigirAlturaAbas();
      
      // 5. Dispara cálculo inicial com delay
      setTimeout(() => {
        recalcular();
        console.info("[M4] Inicialização Completa e Recalcular inicial OK.");
      }, 800);
    },
    
    // Método chamado ao trocar de aba (para re-aplicar máscaras se necessário)
    reinitMasks: initMasks,

    // Método chamado ao trocar de aba (para recalcular resumo)
    refreshResumo: recalcular,
  };
  
  // EXPÕE O MÓDULO GLOBALMENTE
  window.ProdutosForm = ProdutosForm; 

  // Exposição legada (mantida por segurança)
  window.recalcularProduto = recalcular;

})();