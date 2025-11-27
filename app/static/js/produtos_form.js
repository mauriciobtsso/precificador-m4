// ===========================================================
// MÓDULO: PRODUTOS_FORM.JS — Com Suporte a Promoção
// ===========================================================

(() => {
  console.log("[M4] produtos_form.js carregado (v-promo)");

  const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  const el = (id) => document.getElementById(id);
  
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

  let anFornecedor, anLucroAlvo, anPrecoFinal, anFrete, anIPI, anPromoPreco;

  // =========================================
  // Inicialização de Máscaras e Eventos
  // =========================================
  document.addEventListener("DOMContentLoaded", () => {
    if (typeof AutoNumeric === "undefined") {
      console.warn("[M4] AutoNumeric não encontrado. Máscaras desativadas.");
      return;
    }

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
    const initMoney = (selector) => {
      const element = document.querySelector(selector);
      if (!element) return null;
      const an = new AutoNumeric(selector, brlOpts);
      if (element.value && element.value.trim() !== "") {
          an.set(element.value);
      }
      return an;
    };

    // Inicializa campos principais (Restaurando IDs originais)
    anFornecedor = initMoney("#in_preco_fornecedor");
    anLucroAlvo  = initMoney("#in_lucro_alvo");
    anPrecoFinal = initMoney("#in_preco_final");
    anFrete      = initMoney("#in_frete");
    
    // Novo campo de Promoção
    anPromoPreco = initMoney("#in_promo_preco");

    // Campos percentuais simples
    ["in_margem", "in_difal", "in_imposto_venda", "in_desconto"].forEach((id) => {
      const $i = el(id);
      if ($i) {
        try { $i.setAttribute("type", "text"); } catch (_) {} 
        new AutoNumeric(`#${id}`, percOpts);
      }
    });

    // Inicializa IPI (Dinâmico)
    initIpiMask(false);
    
    // Altura das abas
    corrigirAlturaAbas();

    // Dispara cálculo inicial
    setTimeout(() => {
      recalcular();
      console.info("[M4] Recalcular inicial OK.");
    }, 800);
  });

  // ============================================================
  // Máscara dinâmica do IPI
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

  if (ipiTipoSelect) {
      ipiTipoSelect.addEventListener("change", () => {
        initIpiMask(true); 
        recalcular();
      });
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

      // Lógica JS simples para data (opcional, para visualização imediata)
      // O backend é a fonte da verdade, mas aqui damos feedback visual
      let usandoPromo = false;
      if (promoAtiva && promoPreco > 0) {
          const agora = new Date();
          const dtIni = dataInicio ? new Date(dataInicio) : null;
          const dtFim = dataFim ? new Date(dataFim) : null;
          
          // Se tiver datas, verifica intervalo. Se não tiver datas mas estiver ativado, assume ativo.
          if ((!dtIni || agora >= dtIni) && (!dtFim || agora <= dtFim)) {
              precoBase = promoPreco;
              usandoPromo = true;
          }
      }

      // Feedback visual no campo de fornecedor
      const lblFornecedor = el("in_preco_fornecedor");
      if(lblFornecedor) {
          if(usandoPromo) {
              lblFornecedor.classList.add("text-decoration-line-through", "text-muted");
              el("in_promo_preco").classList.add("border-success", "text-success", "fw-bold");
          } else {
              lblFornecedor.classList.remove("text-decoration-line-through", "text-muted");
              el("in_promo_preco")?.classList.remove("border-success", "text-success", "fw-bold");
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
  // Listeners
  // =========================================
  const debounce = (fn, delay = 200) => {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); };
  };

  // Inputs que disparam recalculo
  const idsTriggers = [
      "in_desconto", "in_margem", "in_imposto_venda", "in_difal", "in_ipi", "in_ipi_tipo",
      "in_promo_ativada", "in_promo_inicio", "in_promo_fim" // Novos triggers de promo
  ];

  idsTriggers.forEach((id) => {
    const input = el(id);
    if (input) input.addEventListener("input", debounce(recalcular, 300));
    if (input && input.type === 'checkbox') input.addEventListener("change", recalcular);
  });

  document.addEventListener("autoNumeric:rawValueModified", (e) => {
    // Adicionado in_promo_preco na lista
    if (["in_preco_fornecedor", "in_lucro_alvo", "in_preco_final", "in_frete", "in_ipi", "in_promo_preco"].includes(e.target.id)) {
      recalcular();
    }
  });

  function corrigirAlturaAbas() {
    const tabs = document.querySelectorAll("#produtoTabs .nav-link");
    tabs.forEach(t => t.style.minWidth = "100px");
  }

  // Torna funções globais
  window.recalcularProduto = recalcular;

  // =========================================
  // FOTO (Mantido do original)
  // =========================================
  function initFotoProduto() {
      // ... (código de foto mantido igual) ...
      // Omitido aqui para brevidade, mas deve ser mantido no arquivo final
      const container = document.getElementById("fotoProdutoContainer");
      if (container && container.dataset.bound === "1") return;
      if (container) container.dataset.bound = "1";
      // ... lógica de upload ...
  }
  window.initFotoProduto = initFotoProduto;

})();