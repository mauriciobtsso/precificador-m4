/* ==========================================================
   CONFIGS_MODALS.JS
   CRUD rápido das engrenagens (tipo, marca, calibre, etc.)
   ========================================================== */
(() => {
  console.log("[M4] configs_modals.js carregado");

  // ==========================================
  // Mapa de rotas
  // ==========================================
  const rotaPorTabela = {
    tipos: "tipo",
    marcas: "marca",
    calibres: "calibre",
    funcionamentos: "funcionamento",
    categorias: "categoria"
  };

  // ==========================================
  // Função auxiliar segura para fechar modal
  // ==========================================
  function closeModalById(modalId) {
    const el = document.getElementById(modalId);
    if (!el) {
      console.warn(`[M4] closeModalById: elemento #${modalId} não encontrado`);
      return;
    }

    let instance = bootstrap.Modal.getInstance(el);
    // Se não existe instância, cria e depois esconde
    if (!instance) instance = new bootstrap.Modal(el);
    instance.hide();

    console.log(`[M4] Modal #${modalId} fechado com segurança ✅`);
  }

  // ==========================================
  // Ações de salvar (botões das modais)
  // ==========================================
  document.querySelectorAll(".modal-footer .btn-success[data-tabela]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const tabelaAttr = btn.dataset.tabela || "";
      const tabela = rotaPorTabela[tabelaAttr] || tabelaAttr;
      const inputId = btn.dataset.input;
      const selectId = btn.dataset.select;
      const nome = (document.getElementById(inputId)?.value || "").trim();

      if (!nome) {
        alert("Informe o nome.");
        return;
      }

      btn.disabled = true;
      const originalHTML = btn.innerHTML;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Salvando...';

      try {
        const resp = await fetch(`/produtos/configs/adicionar/${tabela}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nome })
        });

        const data = await resp.json();
        if (!resp.ok || !data.id) throw new Error(data.error || "Erro ao salvar.");

        // Atualiza o <select> vinculado
        const sel = document.getElementById(selectId);
        if (sel) {
          const opt = document.createElement("option");
          opt.value = data.id;
          opt.textContent = nome;
          opt.selected = true;
          sel.appendChild(opt);
        }

        // Fecha o modal de forma segura
        const modalEl = btn.closest(".modal");
        if (modalEl?.id) closeModalById(modalEl.id);

        // Limpa campo
        const input = document.getElementById(inputId);
        if (input) input.value = "";

        // Mostra toast de sucesso, se existir
        const toastEl = document.getElementById("toastCategoria");
        if (toastEl) {
          const bsToast = new bootstrap.Toast(toastEl);
          bsToast.show();
        }

        console.log(`[M4] Novo registro salvo em '${tabela}' → ${nome}`);
      } catch (err) {
        console.error("[M4] Erro ao salvar configuração:", err);
        alert(err.message || "Falha ao salvar.");
      } finally {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
      }
    });
  });
})();
