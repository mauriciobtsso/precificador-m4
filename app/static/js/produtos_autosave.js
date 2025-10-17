/* ==========================================================
   PRODUTOS_AUTOSAVE.JS
   - Auto-save inteligente para formulário de produto
   ========================================================== */
(() => {
  console.log("[M4] produtos_autosave.js carregado");

  const form = document.getElementById("produtoForm");
  if (!form) return;

  const produtoId = form.dataset.produtoId || form.getAttribute("data-produto-id");
  if (!produtoId) {
    console.warn("[M4] Auto-save desativado (produto ainda não salvo)");
    return;
  }

  let timeout = null;
  let saving = false;

  const toastEl = document.getElementById("toastCategoria");
  const toast = new bootstrap.Toast(toastEl);

  function showToast(msg, color = "success", icon = "fa-check-circle") {
    toastEl.className = `toast align-items-center text-bg-${color} border-0`;
    toastEl.querySelector(".toast-body").innerHTML = `<i class="fas ${icon} me-2"></i>${msg}`;
    toast.show();
  }

  async function autoSave() {
    if (saving) return;
    saving = true;
    showToast("Salvando alterações...", "warning", "fa-spinner fa-spin");

    const formData = new FormData(form);
    try {
      const resp = await fetch(`/produtos/auto-save/${produtoId}`, {
        method: "POST",
        body: formData
      });

      if (!resp.ok) throw new Error("Falha ao salvar.");

      const data = await resp.json();
      if (data.success) {
        showToast("Salvo automaticamente", "success", "fa-check-circle");
      } else {
        showToast(data.error || "Erro ao salvar", "danger", "fa-triangle-exclamation");
      }
    } catch (err) {
      console.error("[M4] Auto-save erro:", err);
      showToast("Falha de conexão ou erro interno", "danger", "fa-exclamation-circle");
    } finally {
      saving = false;
    }
  }

  function agendarAutoSave() {
    clearTimeout(timeout);
    timeout = setTimeout(autoSave, 1500); // debounce 1.5s
  }

  // Observa todas as mudanças de campos
  form.querySelectorAll("input, select, textarea").forEach(el => {
    el.addEventListener("input", agendarAutoSave);
    el.addEventListener("change", agendarAutoSave);
  });
})();
/* ==========================================================
   UI REFINADA – Feedback visual de alterações e salvamento
   ========================================================== */
(() => {
  const form = document.getElementById("produtoForm");
  if (!form) return;

  const statusBar = document.createElement("div");
  statusBar.id = "statusBar";
  statusBar.className = "status-bar text-muted small py-1 px-3";
  statusBar.innerHTML = '<i class="fas fa-circle text-success me-1"></i><span>Status:</span> Nenhuma alteração pendente';
  form.parentElement.appendChild(statusBar);

  const toastEl = document.getElementById("toastCategoria");
  const toast = new bootstrap.Toast(toastEl);
  let pendingChanges = new Set();

  function updateTabIndicators() {
    document.querySelectorAll(".nav-link").forEach(tab => {
      const target = tab.dataset.bsTarget;
      if (pendingChanges.has(target)) {
        tab.innerHTML = `${tab.innerHTML.replace("•", "")} <span class="text-orange fw-bold ms-1">•</span>`;
      } else {
        tab.innerHTML = tab.innerHTML.replace(" •", "");
      }
    });
  }

  function updateStatus(text, color = "muted", icon = "fa-circle") {
    statusBar.innerHTML = `<i class="fas ${icon} text-${color} me-1"></i><span>Status:</span> ${text}`;
  }

  async function autoSaveWithUI() {
    updateStatus("Salvando alterações...", "warning", "fa-spinner fa-spin");

    const produtoId = form.dataset.produtoId || form.getAttribute("data-produto-id");
    if (!produtoId) return;

    const formData = new FormData(form);
    try {
      const resp = await fetch(`/produtos/auto-save/${produtoId}`, {
        method: "POST",
        body: formData
      });
      const data = await resp.json();

      if (data.success) {
        pendingChanges.clear();
        updateTabIndicators();
        updateStatus("Salvo automaticamente", "success", "fa-check-circle");
      } else {
        updateStatus("Erro ao salvar", "danger", "fa-triangle-exclamation");
      }
    } catch {
      updateStatus("Falha de conexão", "danger", "fa-exclamation-circle");
    }
  }

  let timeout = null;
  form.querySelectorAll("input, select, textarea").forEach(el => {
    el.addEventListener("input", () => {
      const tabPane = el.closest(".tab-pane");
      if (tabPane) pendingChanges.add("#" + tabPane.id);
      updateTabIndicators();
      updateStatus("Alterações pendentes...", "secondary", "fa-clock");
      clearTimeout(timeout);
      timeout = setTimeout(autoSaveWithUI, 1500);
    });
  });

  // Limpa indicadores ao trocar de aba
  document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tab => {
    tab.addEventListener("shown.bs.tab", () => {
      document.querySelector(tab.dataset.bsTarget)?.classList.add("fade-in");
      setTimeout(() => document.querySelector(tab.dataset.bsTarget)?.classList.remove("fade-in"), 400);
    });
  });
})();

