// ===========================================================
// MÓDULO: PRODUTOS_FORM.JS — Correção Persistência IPI
// ===========================================================

(() => {
  console.log("[M4] produtos_form.js carregado (v-persist-fix)");

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

  let anFornecedor, anLucroAlvo, anPrecoFinal, anFrete, anIPI;

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

    // Inicializa campos principais
    anFornecedor = initMoney("#in_preco_fornecedor");
    anLucroAlvo  = initMoney("#in_lucro_alvo");
    anPrecoFinal = initMoney("#in_preco_final");
    anFrete      = initMoney("#in_frete");

    // Campos percentuais simples
    ["in_margem", "in_difal", "in_imposto_venda"].forEach((id) => {
      const $i = el(id);
      if ($i) {
        try { $i.setAttribute("type", "text"); } catch (_) {} 
        new AutoNumeric(`#${id}`, percOpts);
      }
    });

    // ============================================================
    // Máscara dinâmica do IPI — CORREÇÃO DE PERSISTÊNCIA
    // ============================================================
    const ipiInput = document.getElementById("in_ipi");
    const ipiTipoSelect = document.getElementById("in_ipi_tipo");

    function initIpiMask(forceClear = false) {
      if (!ipiInput || !ipiTipoSelect) return;

      // 1. Captura valor atual
      let valorAtual = 0;
      if (anIPI && AutoNumeric.isManagedByAutoNumeric(ipiInput)) {
          valorAtual = anIPI.getNumber();
      } else {
          valorAtual = num("in_ipi");
      }
      if (forceClear) valorAtual = 0;

      // 2. Remove máscara antiga
      if (anIPI && AutoNumeric.isManagedByAutoNumeric(ipiInput)) {
          anIPI.remove();
      }

      const tipoNovo = ipiTipoSelect.value;
      
      // Opções COMUNS (Adicionado unformatOnSubmit: true CRÍTICO)
      const ipiOpts = {
          digitGroupSeparator: ".",
          decimalCharacter: ",",
          decimalPlaces: 2,
          modifyValueOnWheel: false,
          emptyInputBehavior: "zero",
          unformatOnSubmit: true  // <<--- ESSENCIAL PARA SALVAR CORRETAMENTE
      };

      if (tipoNovo === "fixo" || tipoNovo === "R$") {
        anIPI = new AutoNumeric(ipiInput, { ...ipiOpts, currencySymbol: "R$ " });
      } else {
        anIPI = new AutoNumeric(ipiInput, { ...ipiOpts, suffixText: " %", maximumValue: "1000", minimumValue: "0" });
      }

      // 4. Restaura valor
      anIPI.set(valorAtual);
      ipiInput.dataset.maskType = tipoNovo;
    }

    ipiTipoSelect?.addEventListener("change", () => {
      initIpiMask(true); 
      recalcular();
    });

    initIpiMask(false); // Carga inicial
    corrigirAlturaAbas();

    setTimeout(() => {
      recalcular();
      console.info("[M4] Recalcular inicial OK.");
    }, 800);
  });

  // =========================================
  // Foco automático
  // =========================================
  document.addEventListener("shown.bs.tab", (e) => {
    if (e.target.id === "tab-precos") {
      setTimeout(() => {
          el("in_preco_fornecedor")?.focus();
          recalcular();
      }, 100);
    }
  });

  // =========================================
  // LÓGICA FINANCEIRA
  // =========================================
  function recalcular() {
    try {
      const precoCompra = getAN(anFornecedor);
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

      // 1. Base
      const valorComDesconto = precoCompra * (1 - descFornecedor / 100);
      
      if (el("out_desconto")) el("out_desconto").textContent = brl.format(valorComDesconto || 0);
      if (el("out_frete")) el("out_frete").textContent = brl.format(frete || 0);

      const base = valorComDesconto;

      // 2. IPI
      let valorIPI = 0;
      if (ipiTipo === "%_dentro") {
        const baseSemIPI = base / (1 + ipiValor / 100);
        valorIPI = base - baseSemIPI;
      } else if (ipiTipo === "%") {
        valorIPI = base * (ipiValor / 100);
      } else {
        valorIPI = ipiValor;
      }

      // 3. DIFAL
      const baseDifal = Math.max(base - valorIPI + frete, 0);
      const valorDifal = baseDifal * (difal / 100);
      
      // 4. Custo Total
      const custoTotal = base + valorDifal + frete;

      // 5. Preço
      if (!(precoFinal > 0)) {
        if (lucroAlvo > 0) {
          precoFinal = (custoTotal + lucroAlvo) / (1 - impostoVenda / 100);
        } else if (margem > 0) {
          precoFinal = custoTotal / (1 - margem / 100);
        } else {
          precoFinal = custoTotal;
        }
      }

      // 6. Resultados
      const impostoVendaValor = precoFinal * (impostoVenda / 100);
      const lucroLiquido = precoFinal - custoTotal - impostoVendaValor;

      // Outputs
      const setVal = (id, val) => { const elem = el(id); if (elem) elem.value = brl.format(isFinite(val) ? val : 0); };
      setVal("out_custo_total", custoTotal);
      setVal("out_preco_a_vista", precoFinal);
      setVal("out_lucro_liquido", lucroLiquido);

      if (el("out_ipi")) el("out_ipi").textContent = brl.format(valorIPI || 0);
      if (el("out_difal")) el("out_difal").textContent = brl.format(valorDifal || 0);
      if (el("out_imposto")) el("out_imposto").textContent = brl.format(impostoVendaValor || 0);

      atualizarResumoVisual(lucroLiquido);

      // --- Header ---
      const resumoVenda = document.getElementById("resumo-preco-venda");
      const resumoCusto = document.getElementById("resumo-custo-total");
      const resumoLucro = document.getElementById("resumo-lucro");

      if (resumoVenda) resumoVenda.textContent = `Preço de venda: ${brl.format(precoFinal || 0)}`;
      if (resumoCusto) resumoCusto.textContent = brl.format(custoTotal || 0);

      if (resumoLucro) {
        const margemCalc = precoFinal > 0 ? (lucroLiquido / precoFinal) * 100 : 0;
        resumoLucro.textContent = `${brl.format(lucroLiquido)} (${margemCalc.toFixed(1)}%)`;
        resumoLucro.classList.remove("text-success", "text-danger", "text-muted");
        if (lucroLiquido > 0) resumoLucro.classList.add("text-success");
        else if (lucroLiquido < 0) resumoLucro.classList.add("text-danger");
        else resumoLucro.classList.add("text-muted");
      }

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

  ["in_desconto", "in_margem", "in_imposto_venda", "in_difal", "in_ipi", "in_ipi_tipo"].forEach((id) => {
    const input = el(id);
    if (input) input.addEventListener("input", debounce(recalcular, 300));
  });

  document.addEventListener("autoNumeric:rawValueModified", (e) => {
    if (["in_preco_fornecedor", "in_lucro_alvo", "in_preco_final", "in_frete", "in_ipi"].includes(e.target.id)) {
      recalcular();
    }
  });

  // =========================================
  // FOTO (Mantido)
  // =========================================
  function initFotoProduto() {
    const container = document.getElementById("fotoProdutoContainer");
    if (container && container.dataset.bound === "1") return;
    if (container) container.dataset.bound = "1";

    const inputFile = el("inputFotoProduto");
    const btnSelecionar = el("btnSelecionarFoto");
    const btnRemover = el("btnRemoverFoto");
    const preview = el("fotoProdutoPreview");
    const inputUrl = el("inputFotoUrl");
    const overlay = el("fotoProdutoOverlay");

    if (!inputFile || !btnSelecionar || !preview) return;

    btnSelecionar.addEventListener("click", () => inputFile.click());

    inputFile.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      
      const reader = new FileReader();
      reader.onload = (evt) => (preview.src = evt.target.result);
      reader.readAsDataURL(file);

      if (overlay) overlay.classList.remove("d-none");
      btnSelecionar.disabled = true;
      
      const produtoId = getProdutoId();
      const uploadUrl = produtoId ? `/produtos/${produtoId}/foto` : "/produtos/foto-temp";

      try {
        const fd = new FormData();
        fd.append("foto", file);
        const resp = await fetch(uploadUrl, { method: "POST", body: fd });
        const data = await resp.json();
        
        if (data.success && data.url) {
            if (inputUrl) inputUrl.value = data.url;
            if (btnRemover) btnRemover.classList.remove("d-none");
        } else {
            alert("Erro no upload: " + (data.error || "Desconhecido"));
        }
      } catch (err) {
        console.error("Upload falhou", err);
      } finally {
        if (overlay) overlay.classList.add("d-none");
        btnSelecionar.disabled = false;
      }
    });

    if (btnRemover) {
        btnRemover.addEventListener("click", async () => {
            if (!confirm("Remover foto?")) return;
            const produtoId = getProdutoId();
            if (produtoId) {
                await fetch(`/produtos/${produtoId}/foto`, { method: "DELETE" });
            }
            preview.src = "/static/img/placeholder.jpg";
            if (inputUrl) inputUrl.value = "";
            if (inputFile) inputFile.value = "";
            btnRemover.classList.add("d-none");
        });
    }
  }

  function corrigirAlturaAbas() {
    const tabs = document.querySelectorAll("#produtoTabs .nav-link");
    tabs.forEach(t => t.style.minWidth = "100px");
  }

  window.recalcularProduto = recalcular;
  window.initFotoProduto = initFotoProduto;

  document.addEventListener("DOMContentLoaded", () => {
      if(window.initFotoProduto) window.initFotoProduto();
  });

})();