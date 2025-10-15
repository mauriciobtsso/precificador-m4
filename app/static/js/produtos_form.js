// ===============================
// MÓDULO: PRODUTOS_FORM.JS
// ===============================
// Gerencia máscaras, cálculos automáticos, 
// e integração do modal de "Nova Categoria" via AJAX.
// ===============================

(() => {
  console.log("[M4] produtos_form.js carregado");

  // ========= CONFIGURAÇÕES GERAIS =========
  const brl = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL"
  });

  const el = (id) => document.getElementById(id);
  const num = (id) => parseFloat((el(id)?.value || "0").replace(",", ".")) || 0;
  const getAN = (an) => parseFloat(an?.getNumber()) || 0;

  // ========= INICIALIZAÇÃO DE MÁSCARAS =========
  const anOpts = {
    digitGroupSeparator: ".",
    decimalCharacter: ",",
    decimalPlaces: 2,
    currencySymbol: "R$ ",
    currencySymbolPlacement: "p",
    unformatOnSubmit: true,
    emptyInputBehavior: "zero",
    modifyValueOnWheel: false
  };

  let anFornecedor, anLucroAlvo, anPrecoFinal, anFrete;

  document.addEventListener("DOMContentLoaded", () => {
    if (typeof AutoNumeric === "undefined") {
      console.warn("[M4] AutoNumeric não encontrado. Máscaras desativadas.");
      return;
    }

    anFornecedor = new AutoNumeric("#in_preco_fornecedor", anOpts);
    anLucroAlvo  = new AutoNumeric("#in_lucro_alvo", anOpts);
    anPrecoFinal = new AutoNumeric("#in_preco_final", anOpts);
    anFrete      = new AutoNumeric("#in_frete", anOpts);

    // força uppercase no campo código
    const codigoInput = el("codigo");
    if (codigoInput) {
      codigoInput.addEventListener("input", () => {
        codigoInput.value = codigoInput.value.toUpperCase();
      });
    }

    // dispara cálculo inicial
    recalcular();
  });

  // ========= FUNÇÃO PRINCIPAL DE CÁLCULO =========
  function recalcular() {
    try {
      const precoCompra   = getAN(anFornecedor);
      const descFornecedor= num("in_desconto");
      const margem        = num("in_margem");
      const impostoVenda  = num("in_imposto_venda");
      const difal         = num("in_difal");
      const ipiValor      = num("in_ipi");
      const ipiTipo       = el("in_ipi_tipo")?.value || "%_dentro";
      const frete         = getAN(anFrete);

      const lucroAlvo     = getAN(anLucroAlvo);
      let precoFinal      = getAN(anPrecoFinal);

      const valorComDesconto = precoCompra * (1 - descFornecedor / 100);
      if (el("out_desconto")) el("out_desconto").textContent = brl.format(valorComDesconto);
      if (el("out_frete")) el("out_frete").textContent = brl.format(frete);

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
      const baseDifal  = Math.max(base - valorIPI + frete, 0);
      const valorDifal = baseDifal * (difal / 100);

      // Custo total
      const custoTotal = base + valorDifal + frete;

      // Preço sugerido
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

      if (el("out_custo_total")) el("out_custo_total").value = brl.format(custoTotal);
      if (el("out_preco_a_vista")) el("out_preco_a_vista").value = brl.format(precoFinal);
      if (el("out_lucro_liquido")) el("out_lucro_liquido").value = brl.format(lucroLiquido);

      if (el("out_ipi")) el("out_ipi").textContent = brl.format(valorIPI);
      if (el("out_difal")) el("out_difal").textContent = brl.format(valorDifal);
      if (el("out_imposto")) el("out_imposto").textContent = brl.format(impostoVendaValor);
    } catch (err) {
      console.error("[M4] Erro no cálculo automático:", err);
    }
  }

  // ========= EVENTOS =========
  const campos = [
    "in_desconto", "in_margem", "in_imposto_venda",
    "in_difal", "in_ipi", "in_ipi_tipo"
  ];

  campos.forEach((id) => {
    const input = el(id);
    if (input) input.addEventListener("input", recalcular);
  });

  document.addEventListener("autoNumeric:rawValueModified", (e) => {
    if (
      ["in_preco_fornecedor", "in_lucro_alvo", "in_preco_final", "in_frete"].includes(
        e.target.id
      )
    ) {
      recalcular();
    }
  });

  // ========= MODAL "NOVA CATEGORIA" =========
  const btnSalvarCategoria = document.getElementById("btnSalvarCategoria");
  if (btnSalvarCategoria) {
    btnSalvarCategoria.addEventListener("click", async () => {
      const nome = (el("nc_nome")?.value || "").trim();
      const pai  = el("nc_pai")?.value || "";
      const desc = el("nc_descricao")?.value || "";

      if (!nome) {
        alert("Informe o nome da categoria.");
        return;
      }

      try {
        const resp = await fetch("/categorias/adicionar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            nome: nome,
            pai_id: pai || null,
            descricao: desc || null
          })
        });

        if (!resp.ok) throw new Error(await resp.text());

        const data = await resp.json();
        if (!data || !data.id) throw new Error("Resposta inesperada.");

        // Atualiza o select principal
        const sel = el("categoria_id");
        const opt = document.createElement("option");
        opt.value = data.id;
        opt.textContent = data.nome;
        sel.appendChild(opt);
        sel.value = String(data.id);

        // Limpa o modal
        el("nc_nome").value = "";
        el("nc_pai").value = "";
        el("nc_descricao").value = "";

        // Fecha o modal
        const modalEl = el("modalNovaCategoria");
        const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
        modal.hide();

        // Mostra toast de sucesso
        const toastEl = el("toastCategoria");
        const toast = new bootstrap.Toast(toastEl);
        toast.show();

      } catch (err) {
        console.error("[M4] Erro ao adicionar categoria:", err);
        alert("Não foi possível adicionar a categoria. Tente novamente.");
      }
    });
  }

  // ========= EXPÕE RELOAD MANUAL (opcional) =========
  window.recalcularProduto = recalcular;

})();
