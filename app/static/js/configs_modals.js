/* ==========================================================
   CONFIGS_MODALS.JS - VERSÃO ATUALIZADA M4
   CRUD rápido com suporte a upload de Logo para Marcas
   ========================================================== */
(() => {
  console.log("[M4] configs_modals.js carregado com suporte a upload");

  const rotaPorTabela = {
    tipos: "tipo",
    marcas: "marca",
    calibres: "calibre",
    funcionamentos: "funcionamento",
    categorias: "categoria"
  };

  function closeModalById(modalId) {
    const el = document.getElementById(modalId);
    if (!el) return;
    let instance = bootstrap.Modal.getInstance(el);
    if (!instance) instance = new bootstrap.Modal(el);
    instance.hide();
  }

  document.querySelectorAll(".modal-footer .btn-success[data-tabela]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const tabelaAttr = btn.dataset.tabela || "";
      const tabela = rotaPorTabela[tabelaAttr] || tabelaAttr;
      const inputId = btn.dataset.input;
      const selectId = btn.dataset.select;
      const nomeInput = document.getElementById(inputId);
      const nome = (nomeInput?.value || "").trim();

      if (!nome) {
        alert("Por favor, informe o nome.");
        return;
      }

      btn.disabled = true;
      const originalHTML = btn.innerHTML;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Salvando...';

      try {
        let response;
        
        // --- LÓGICA ESPECIAL PARA MARCA (ENVIO DE ARQUIVO) ---
        if (tabela === "marca") {
          const formData = new FormData();
          formData.append("nome", nome);
          
          // Captura a logo se o campo existir e tiver arquivo
          const logoInput = document.getElementById("nm_logo");
          if (logoInput && logoInput.files[0]) {
            formData.append("logo", logoInput.files[0]);
          }

          response = await fetch(`/produtos/configs/adicionar/marca`, {
            method: "POST",
            body: formData // O navegador define o Content-Type automaticamente para FormData
          });
        } else {
          // --- LÓGICA PADRÃO PARA OUTROS (JSON) ---
          response = await fetch(`/produtos/configs/adicionar/${tabela}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nome })
          });
        }

        const data = await response.json();
        
        if (!response.ok) {
          throw new Error(data.error || "Erro ao salvar no servidor.");
        }

        // 1. Atualiza o <select> se ele existir (uso no formulário de produto)
        const sel = document.getElementById(selectId);
        if (sel) {
          const opt = document.createElement("option");
          opt.value = data.id;
          opt.textContent = nome;
          opt.selected = true;
          sel.appendChild(opt);
          sel.dispatchEvent(new Event('change')); // Avisa outros scripts que mudou
        }

        // 2. Fecha o modal
        const modalEl = btn.closest(".modal");
        if (modalEl?.id) closeModalById(modalEl.id);

        // 3. Limpa os campos
        if (nomeInput) nomeInput.value = "";
        const logoInput = document.getElementById("nm_logo");
        if (logoInput) logoInput.value = "";

        // 4. Feedback visual (Toast)
        const toastEl = document.getElementById("toastCategoria");
        if (toastEl) {
          new bootstrap.Toast(toastEl).show();
        } else {
          console.log(`[M4] Sucesso: ${nome} salvo.`);
        }

        // 5. Se estiver na tela de listagem de marcas, recarrega para mostrar a nova
        if (window.location.href.includes('/configs/')) {
            window.location.reload();
        }

      } catch (err) {
        console.error("[M4] Erro:", err);
        alert(err.message);
      } finally {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
      }
    });
  });
})();