// ===============================
// MÓDULO: PRODUTOS_HISTORICO.JS
// Atualiza a aba de histórico dinamicamente
// ===============================

(() => {
  console.log("[M4] produtos_historico.js carregado");

  // Função auxiliar para atualizar a aba histórico
  async function recarregarHistorico(produtoId) {
    try {
      const resp = await fetch(`/produtos/${produtoId}/historico/fragment`);
      const html = await resp.text();
      const container = document.querySelector("#aba-historico");
      if (container) {
        container.innerHTML = html;
        inicializarTooltips();
      }
    } catch (err) {
      console.error("[M4] Erro ao recarregar histórico:", err);
    }
  }

  // Inicializa tooltips bootstrap (usado após reload)
  function inicializarTooltips() {
    const tooltipTriggerList = [].slice.call(
      document.querySelectorAll('[data-bs-toggle="tooltip"]')
    );
    tooltipTriggerList.map((el) => new bootstrap.Tooltip(el));
  }

  // Evento de reversão
  document.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("[data-reverter-id]");
    if (!btn) return;

    const histId = btn.dataset.reverterId;
    const campo = btn.dataset.campo;
    const produtoId = document.querySelector("[data-produto-id]")?.dataset.produtoId;

    if (!histId || !produtoId) return;
    if (!confirm(`Deseja reverter o campo "${campo}" para o valor anterior?`)) return;

    btn.disabled = true;
    try {
      const resp = await fetch(`/produtos/historico/${histId}/reverter`, { method: "POST" });
      const data = await resp.json();

      if (data.success) {
        alert(data.message || "Valor revertido com sucesso!");
        await recarregarHistorico(produtoId);
      } else {
        alert(data.error || "Erro ao reverter valor.");
      }
    } catch (err) {
      console.error("[M4] Erro ao reverter:", err);
      alert("Erro inesperado ao tentar reverter.");
    } finally {
      btn.disabled = false;
    }
  });

  // Expõe globalmente (para integração com auto-save)
  window.recarregarHistorico = recarregarHistorico;
})();
// ============================================================
// ATUALIZA CONTADOR DE HISTÓRICO DINAMICAMENTE
// ============================================================
window.refreshHistoricoCount = async (produtoId) => {
  try {
    const resp = await fetch(`/produtos/fragment/historico/${produtoId}/count`);
    if (!resp.ok) throw new Error("Falha ao buscar contador de histórico");
    const data = await resp.json();

    const aba = document.querySelector('#produtoTabs .nav-link[data-bs-target="#abaHistorico"]');
    if (aba && data.count !== undefined) {
      const label = `<i class="fas fa-history me-1"></i> Histórico (${data.count})`;
      aba.innerHTML = label;
    }
  } catch (err) {
    console.error("[M4] Erro ao atualizar contador de histórico:", err);
  }
};
