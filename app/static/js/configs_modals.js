/* ==========================================================
   CONFIGS_MODALS.JS
   - Gera CRUD rápido das engrenagens (tipo, marca, calibre, etc.)
   ========================================================== */
(() => {
  console.log("[M4] configs_modals.js carregado");

  const rotaPorTabela = {
    tipos: "tipo",
    marcas: "marca",
    calibres: "calibre",
    funcionamentos: "funcionamento",
    categorias: "categoria"
  };

  document.querySelectorAll(".modal-footer .btn-success[data-tabela]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const tabelaAttr = btn.dataset.tabela || "";
      const tabela = rotaPorTabela[tabelaAttr] || tabelaAttr;
      const inputId = btn.dataset.input;
      const selectId = btn.dataset.select;
      const nome = (document.getElementById(inputId)?.value || "").trim();

      if (!nome) return alert("Informe o nome.");

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

        const sel = document.getElementById(selectId);
        if (sel) {
          const opt = document.createElement("option");
          opt.value = data.id;
          opt.textContent = nome;
          opt.selected = true;
          sel.appendChild(opt);
        }

        const modalEl = btn.closest(".modal");
        bootstrap.Modal.getInstance(modalEl)?.hide();
        document.getElementById(inputId).value = "";

        new bootstrap.Toast(document.getElementById("toastCategoria")).show();
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
