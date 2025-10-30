// ===========================================================
// MÓDULO: PRODUTOS_FORM.JS — Fase 5.2 + 5.4 + FOTO (revisado final)
// ===========================================================

(() => {
  console.log("[M4] produtos_form.js carregado");

  const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  const el = (id) => document.getElementById(id);
  const num = (id) => parseFloat((el(id)?.value || "0").replace(",", ".")) || 0;
  const getAN = (an) => parseFloat(an?.getNumber?.()) || 0;

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

    // Dinheiro
    anFornecedor = new AutoNumeric("#in_preco_fornecedor", brlOpts);
    anLucroAlvo  = new AutoNumeric("#in_lucro_alvo", brlOpts);
    anPrecoFinal = new AutoNumeric("#in_preco_final", brlOpts);
    anFrete      = new AutoNumeric("#in_frete", brlOpts);

    // Campos percentuais (exceto IPI, tratado separadamente)
    ["in_margem", "in_difal", "in_imposto_venda"].forEach((id) => {
      const $i = el(id);
      if ($i) {
        try { $i.setAttribute("type", "text"); } catch (_) {}
        new AutoNumeric(`#${id}`, percOpts);
      }
    });

    // ============================================================
    // Máscara dinâmica do IPI (% ou R$)
    // ============================================================
    const ipiInput = document.getElementById("in_ipi");
    const ipiTipoSelect = document.getElementById("in_ipi_tipo");

    function initIpiMask(forceClear = false) {
      if (!ipiInput || !ipiTipoSelect) return;

      const tipoNovo = ipiTipoSelect.value;
      const tipoAtual = ipiInput.dataset.maskType;

      // evita duplicação
      if (tipoAtual === tipoNovo && anIPI && AutoNumeric.isManagedByAutoNumeric(ipiInput)) return;

      // remove máscara anterior com segurança
      if (anIPI && AutoNumeric.isManagedByAutoNumeric(ipiInput)) {
        try { anIPI.remove(); } catch (e) { console.warn("[M4] Remoção antiga de IPI:", e); }
      }

      if (forceClear) ipiInput.value = "";

      const moneyOptions = {
        currencySymbol: "R$ ",
        decimalCharacter: ",",
        digitGroupSeparator: ".",
        decimalPlaces: 2,
        modifyValueOnWheel: false,
      };

      const percentOptions = {
        suffixText: " %",
        decimalCharacter: ",",
        digitGroupSeparator: ".",
        decimalPlaces: 2,
        modifyValueOnWheel: false,
        maximumValue: "1000",
        minimumValue: "0",
      };

      if (tipoNovo === "fixo") {
        anIPI = new AutoNumeric(ipiInput, moneyOptions);
      } else {
        anIPI = new AutoNumeric(ipiInput, percentOptions);
      }

      ipiInput.dataset.maskType = tipoNovo;
      console.log(`[M4] Máscara IPI configurada como: ${tipoNovo}`);
    }

    ipiTipoSelect?.addEventListener("change", () => {
      initIpiMask(true);
      recalcular();
    });

    document.addEventListener("DOMContentLoaded", () => initIpiMask(false));
    initIpiMask(false);

    corrigirAlturaAbas();

    setTimeout(() => {
      recalcular();
      console.info("[M4] Recalcular inicial forçado (produto carregado)");
    }, 600);
  });

  // =========================================
  // Foco automático ao abrir aba "Preços"
  // =========================================
  document.addEventListener("shown.bs.tab", (e) => {
    if (e.target.id === "tab-precos") {
      setTimeout(() => el("in_preco_fornecedor")?.focus(), 100);
    }
  });

  // =========================================
  // Função principal de cálculo
  // =========================================
  function recalcular() {
    try {
      const precoCompra = getAN(anFornecedor);
      const descFornecedor = num("in_desconto");
      const margem = num("in_margem");
      const impostoVenda = num("in_imposto_venda");
      const difal = num("in_difal");
      const frete = getAN(anFrete);
      const lucroAlvo = getAN(anLucroAlvo);
      let precoFinal = getAN(anPrecoFinal);

      const ipiTipo = el("in_ipi_tipo")?.value || "%_dentro";
      let ipiValor = num("in_ipi");
      if (ipiTipo === "fixo") {
        ipiValor = getAN(anIPI);
      }

      const valorComDesconto = precoCompra * (1 - descFornecedor / 100);
      if (el("out_desconto")) el("out_desconto").textContent = brl.format(valorComDesconto || 0);
      if (el("out_frete")) el("out_frete").textContent = brl.format(frete || 0);
      const base = valorComDesconto;

      let valorIPI = 0;
      if (ipiTipo === "%_dentro") {
        const baseSemIPI = base / (1 + ipiValor / 100);
        valorIPI = base - baseSemIPI;
      } else if (ipiTipo === "%") {
        valorIPI = base * (ipiValor / 100);
      } else {
        valorIPI = ipiValor;
      }

      const baseDifal = Math.max(base - valorIPI + frete, 0);
      const valorDifal = baseDifal * (difal / 100);
      const custoTotal = base + valorDifal + frete;

      if (!(precoFinal > 0)) {
        if (lucroAlvo > 0) {
          precoFinal = (custoTotal + lucroAlvo) / (1 - impostoVenda / 100);
        } else if (margem > 0) {
          precoFinal = custoTotal / (1 - margem / 100);
        } else {
          precoFinal = custoTotal;
        }
      }

      const impostoVendaValor = precoFinal * (impostoVenda / 100);
      const lucroLiquido = precoFinal - custoTotal - impostoVendaValor;

      const setVal = (id, val) => {
        const elem = el(id);
        if (!elem) return;
        const value = isFinite(val) ? val : 0;
        elem.value = brl.format(value);
      };

      setVal("out_custo_total", custoTotal);
      setVal("out_preco_a_vista", precoFinal);
      setVal("out_lucro_liquido", lucroLiquido);

      if (el("out_ipi")) el("out_ipi").textContent = brl.format(valorIPI || 0);
      if (el("out_difal")) el("out_difal").textContent = brl.format(valorDifal || 0);
      if (el("out_imposto")) el("out_imposto").textContent = brl.format(impostoVendaValor || 0);

      atualizarResumoVisual(lucroLiquido);

      ["out_custo_total", "out_preco_a_vista", "out_lucro_liquido"].forEach(id => {
        const campo = el(id);
        if (!campo) return;
        campo.classList.remove("feedback-alterado", "feedback-lucro", "feedback-prejuizo");

        if (id === "out_lucro_liquido") {
          if (lucroLiquido > 0) campo.classList.add("feedback-lucro");
          else if (lucroLiquido < 0) campo.classList.add("feedback-prejuizo");
          else campo.classList.add("feedback-alterado");
        } else {
          campo.classList.add("feedback-alterado");
        }

        setTimeout(() => campo.classList.remove("feedback-alterado", "feedback-lucro", "feedback-prejuizo"), 1000);
      });

      const resumoVenda = document.getElementById("resumo-preco-venda");
      const resumoCusto = document.getElementById("resumo-custo-total");
      const resumoLucro = document.getElementById("resumo-lucro");

      if (resumoVenda) resumoVenda.textContent = `Preço de venda: ${brl.format(precoFinal || 0)}`;
      if (resumoCusto) resumoCusto.textContent = brl.format(custoTotal || 0);

      if (resumoLucro) {
        const margemCalc = precoFinal > 0 ? (lucroLiquido / precoFinal) * 100 : 0;
        resumoLucro.textContent = `${brl.format(lucroLiquido)} (${margemCalc.toFixed(1)}%)`;
        resumoLucro.classList.toggle("text-success", lucroLiquido > 0);
        resumoLucro.classList.toggle("text-danger", lucroLiquido <= 0);
      }

      console.info("[M4] Recalcular completo ✅");
    } catch (err) {
      console.error("[M4] Erro no cálculo automático:", err);
    }
  }

  // =========================================
  // Atualização visual do resumo
  // =========================================
  function atualizarResumoVisual(lucroLiquido) {
    const lucroEl = el("out_lucro_liquido");
    const custoEl = el("out_custo_total");
    const precoEl = el("out_preco_a_vista");
    if (!lucroEl) return;

    const classes = ["valor-positivo", "valor-negativo", "valor-neutro"];
    [lucroEl, custoEl, precoEl].forEach((e) => e?.classList.remove(...classes));

    [lucroEl, custoEl, precoEl].forEach((e) => {
      e?.classList.add("animate-resumo");
      setTimeout(() => e?.classList.add("done"), 50);
      setTimeout(() => e?.classList.remove("animate-resumo", "done"), 400);
    });

    if (lucroLiquido > 0.009) lucroEl.classList.add("valor-positivo");
    else if (lucroLiquido < -0.009) lucroEl.classList.add("valor-negativo");
    else lucroEl.classList.add("valor-neutro");
  }

  // =========================================
  // Eventos e debounce ajustado
  // =========================================
  const campos = ["in_desconto", "in_margem", "in_imposto_venda", "in_difal", "in_ipi", "in_ipi_tipo"];
  campos.forEach((id) => {
    const input = el(id);
    if (input) {
      input.addEventListener("input", debounce(() => {
        input.classList.add("campo-editando");
        setTimeout(() => input.classList.remove("campo-editando"), 1500);
        recalcular();
      }, 300));
    }
  });

  document.addEventListener("autoNumeric:rawValueModified", (e) => {
    if (["in_preco_fornecedor", "in_lucro_alvo", "in_preco_final", "in_frete"].includes(e.target.id)) {
      recalcular();
    }
  });

  // =========================================
  // FOTO DO PRODUTO — Preview + Upload R2
  // =========================================
  function initFotoProduto() {
    const container = document.getElementById("fotoProdutoContainer");
    if (container && container.dataset.bound === "1") return;
    if (container) container.dataset.bound = "1";

    console.log("[M4] initFotoProduto() iniciado");
    const inputFile = el("inputFotoProduto");
    const btnSelecionar = el("btnSelecionarFoto");
    const btnRemover = el("btnRemoverFoto");
    const preview = el("fotoProdutoPreview");
    const inputUrl = el("inputFotoUrl");
    const overlay = el("fotoProdutoOverlay");
    const hoverOverlay = el("fotoProdutoHoverOverlay");

    if (!inputFile || !btnSelecionar || !preview || !inputUrl || !overlay || !hoverOverlay) {
      console.warn("[M4] Elementos da foto não encontrados.");
      return;
    }

    btnSelecionar.addEventListener("click", () => inputFile.click());

    inputFile.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (evt) => (preview.src = evt.target.result);
      reader.readAsDataURL(file);

      if (overlay) overlay.classList.remove("d-none");
      if (hoverOverlay) hoverOverlay.style.opacity = '0';
      btnSelecionar.disabled = true;
      btnSelecionar.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Enviando...';

      const produtoId = getProdutoId();
      const uploadUrl = produtoId ? `/produtos/${produtoId}/foto` : "/foto-temp";

      try {
        const fd = new FormData();
        fd.append("foto", file);
        const resp = await fetch(uploadUrl, { method: "POST", body: fd });
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        if (!data?.success || !data?.url) throw new Error("Upload falhou.");

        preview.src = data.url.split("#")[0];
        inputUrl.value = data.url;
        btnRemover?.classList.remove("d-none");

        console.log("[M4] Upload concluído:", data.url);

        try {
          const r = await fetch(`/produtos/${produtoId}/foto-url?ts=${Date.now()}`, { cache: "no-store" });
          if (r.ok) {
            const j = await r.json();
            if (j?.success && j?.url) {
              preview.src = j.url;
              console.log("[M4] Preview atualizado com URL temporária.");
            }
          }
        } catch (_e) {
          console.warn("[M4] Falha ao tentar obter URL assinada.", _e);
        }

      } catch (err) {
        console.error("[M4] Erro ao enviar foto:", err);
      } finally {
        if (overlay) overlay.classList.add("d-none");
        if (hoverOverlay) hoverOverlay.style.opacity = '0';
        btnSelecionar.disabled = false;
        btnSelecionar.innerHTML = '<i class="fas fa-camera me-1"></i> Alterar foto';
      }
    });

    if (btnRemover) {
      btnRemover.addEventListener("click", async () => {
        const currentUrl = inputUrl.value;
        const produtoId = getProdutoId();

        if (!produtoId && currentUrl.includes("#")) {
          const tempKey = currentUrl.split("#")[1];
          try {
            await fetch(`/foto-temp/${tempKey}`, { method: "DELETE" });
          } catch (err) {
            console.warn("[M4] Falha ao remover foto temporária:", err);
          }
        }

        preview.src = "/static/img/placeholder.jpg";
        if (inputFile) inputFile.value = "";
        inputUrl.value = "";
        btnRemover.classList.add("d-none");
      });
    }
  }

  // =========================================
  // Correção visual das abas
  // =========================================
  function corrigirAlturaAbas() {
    const tabs = document.querySelectorAll("#produtoTabs .nav-link");
    tabs.forEach((tab) => {
      tab.style.minWidth = "120px";
      tab.style.textAlign = "center";
      tab.style.transition = "none";
    });
  }

  // =========================================
  // Debounce helper
  // =========================================
  function debounce(fn, delay = 200) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  }

  // =========================================
  // Carrega a URL pré-assinada para o preview inicial
  // =========================================
  function carregarFotoInicial() {
    const produtoId = getProdutoId();
    const inputUrl = el("inputFotoUrl");
    const preview = el("fotoProdutoPreview");

    if (!produtoId || !inputUrl || !preview || !inputUrl.value || !inputUrl.value.includes('r2.dev')) return;

    fetch(`/produtos/${produtoId}/foto-url?ts=${Date.now()}`, { cache: "no-store" })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d?.success && d.url) {
          preview.src = d.url;
          console.log("[M4] Preview inicial atualizado.");
        } else {
          console.warn("[M4] Falha ao obter URL assinada inicial.");
        }
      })
      .catch(err => console.error("[M4] Erro de rede:", err));
  }

  // ============================================================
  // RESUMO FINANCEIRO — Atualiza valores no topo
  // ============================================================
  function refreshResumo() {
    try {
      const precoVendaEl = document.querySelector("#in_preco_final");
      const precoFornecedorEl = document.querySelector("#in_preco_fornecedor");
      const precoVenda = precoVendaEl ? parseFloat(precoVendaEl.value.replace(/[^\d,]/g, "").replace(",", ".")) || 0 : 0;
      const precoFornecedor = precoFornecedorEl ? parseFloat(precoFornecedorEl.value.replace(/[^\d,]/g, "").replace(",", ".")) || 0 : 0;
      const frete = getAN(anFrete);
      const ipi = num("in_ipi");
      const difal = num("in_difal");
      const impostoVenda = num("in_imposto_venda");

      const custoTotal = precoFornecedor + frete + (precoFornecedor * (ipi / 100)) + (precoFornecedor * (difal / 100));
      const lucroLiquido = precoVenda - custoTotal - (precoVenda * (impostoVenda / 100));
      const margem = precoVenda > 0 ? (lucroLiquido / precoVenda) * 100 : 0;

      const elVenda = document.getElementById("resumo-preco-venda");
      const elCusto = document.getElementById("resumo-custo-total");
      const elLucro = document.getElementById("resumo-lucro");

      if (elVenda) elVenda.textContent = `Preço de venda: ${brl.format(precoVenda)}`;
      if (elCusto) elCusto.textContent = brl.format(custoTotal);

      if (elLucro) {
        elLucro.textContent = `${brl.format(lucroLiquido)} (${margem.toFixed(1)}%)`;
        elLucro.classList.toggle("text-success", lucroLiquido > 0);
        elLucro.classList.toggle("text-danger", lucroLiquido <= 0);
      }

      console.log("[M4] Resumo atualizado ✅");
    } catch (err) {
      console.warn("[M4] Erro ao atualizar resumo:", err);
    }
  }

  // =========================================
  // Exposição manual
  // =========================================
  window.recalcularProduto = recalcular;
  window.initFotoProduto = initFotoProduto;

  document.addEventListener("DOMContentLoaded", () => {
    if (typeof window.initFotoProduto === "function") {
      try { window.initFotoProduto(); } catch(e){ console.warn("[M4] initFotoProduto falhou:", e); }
    }
    carregarFotoInicial();
  });

})();
