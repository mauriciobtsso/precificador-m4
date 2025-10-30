// ============================================================
// MÓDULO: PRODUTOS_AUTOSAVE.JS — Sprint 6D (inteligente + UI)
// ============================================================

(() => {
  console.log("[M4] produtos_autosave.js iniciado");

  const form = document.getElementById("produtoForm");
  if (!form) return;

  const produtoId = document.querySelector("[data-produto-id]")?.dataset?.produtoId;
  if (!produtoId) {
    console.warn("[M4] Autosave desativado — produto ainda não salvo.");
    return;
  }

  let autosaveTimer = null;
  let isSaving = false;
  const delay = 1500; // 1.5 segundos de inatividade

  // Cria elemento visual de status (fallback, caso header não exista)
  const statusEl = document.createElement("div");
  statusEl.className = "text-muted small mt-1";
  statusEl.style.display = "none";
  form.appendChild(statusEl);

  // ============================================================
  // TOAST DE CONFIRMAÇÃO GLOBAL
  // ============================================================
  const showToast = (message = "Alterações salvas com sucesso", type = "success") => {
    const toastEl = document.getElementById("toastAutosave");
    if (!toastEl) return;

    // Ajusta cor conforme tipo
    toastEl.classList.remove("text-bg-success", "text-bg-danger", "text-bg-warning");
    if (type === "error") toastEl.classList.add("text-bg-danger");
    else if (type === "warn") toastEl.classList.add("text-bg-warning");
    else toastEl.classList.add("text-bg-success");

    toastEl.querySelector(".toast-body").textContent = message;
    const bsToast = new bootstrap.Toast(toastEl);
    bsToast.show();
  };

  // ============================================================
  // ÍCONE DE STATUS NO CABEÇALHO (opcional, com fallback)
  // ============================================================
  const iconEl = document.getElementById("autosave-icon");
  const textEl = document.getElementById("autosave-text");

  const setStatus = (state, msg = "") => {
    // Header com ícone/texto (prioritário)
    if (iconEl && textEl) {
      iconEl.className = "fas me-1";
      iconEl.style.transition = "color 0.3s ease";

      switch (state) {
        case "saving":
          iconEl.classList.add("fa-circle-notch", "fa-spin", "text-warning");
          textEl.textContent = msg || "Salvando...";
          break;
        case "success":
          iconEl.classList.add("fa-check-circle", "text-success");
          textEl.textContent = msg || "Alterações salvas";
          break;
        case "error":
          iconEl.classList.add("fa-exclamation-circle", "text-danger");
          textEl.textContent = msg || "Erro ao salvar";
          break;
        default:
          iconEl.classList.add("fa-save", "text-muted");
          textEl.textContent = msg || "";
      }
    } else {
      // Fallback visual no final do form
      if (state === "saving") {
        statusEl.style.display = "inline-block";
        statusEl.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i> Salvando...`;
      } else if (state === "success") {
        const hora = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
        statusEl.innerHTML = `<i class="fas fa-check-circle text-success me-1"></i> Alterações salvas às ${hora}`;
        setTimeout(() => (statusEl.style.display = "none"), 2500);
      } else if (state === "error") {
        statusEl.innerHTML = `<i class="fas fa-exclamation-circle text-danger me-1"></i> Erro ao salvar`;
      }
    }
  };

  // ============================================================
  // FUNÇÕES AUXILIARES
  // ============================================================
  const marcarAbaAlterada = () => {
    const activeTab = document.querySelector("#produtoTabs .nav-link.active");
    if (activeTab && !activeTab.classList.contains("tab-changed")) {
      activeTab.classList.add("tab-changed");
      activeTab.innerHTML = activeTab.textContent + " <span class='text-warning'>•</span>";
    }
  };

  const limparMarcador = () => {
    document.querySelectorAll("#produtoTabs .nav-link").forEach(tab => {
      tab.innerHTML = tab.textContent.replace(" •", "");
      tab.classList.remove("tab-changed");
    });
  };

  const coletarDados = () => {
    const data = {};
    form.querySelectorAll("input, select, textarea").forEach(el => {
      if (el.name && el.value !== undefined) {
        data[el.name] = el.value;
      }
    });
    return data;
  };

  const atualizarUltimaModificacao = (texto) => {
    const alvo = document.querySelector(".text-muted.small.mt-1");
    if (alvo) alvo.innerHTML = `<i class="far fa-clock me-1"></i> Última modificação: ${texto}`;
  };

  // ============================================================
  // MEMÓRIA LOCAL: último estado salvo do formulário
  // ============================================================
  let lastSavedData = coletarDados(); // semente inicial ao carregar a página

  const houveMudanca = (curr, prev) => {
    // compara por chave/valor de forma simples
    const keys = new Set([...Object.keys(curr), ...Object.keys(prev)]);
    for (const k of keys) {
      if ((curr[k] ?? "") !== (prev[k] ?? "")) return true;
    }
    return false;
  };

  // ============================================================
  // ENVIA AUTOSAVE VIA FETCH (com salvamento inteligente)
  // ============================================================
  const salvarAutomaticamente = async () => {
    if (isSaving) return;

    const data = coletarDados();

    // Verifica se algo mudou desde o último salvamento
    if (!houveMudanca(data, lastSavedData)) {
      console.log("[M4] Nenhuma alteração detectada — autosave cancelado.");
      return;
    }

    isSaving = true;
    setStatus("saving"); // ícone/label no header
    // fallback extra, caso não tenha header
    statusEl.style.display = "inline-block";
    statusEl.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i> Salvando...`;

    try {
      console.log("[M4] Autosave enviado → campos:", Object.keys(data));

      const resp = await fetch(`/produtos/autosave/${produtoId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (!resp.ok) throw new Error("Falha ao salvar no servidor");

      const result = await resp.json();

      if (result.success) {
        console.log("[M4] Autosave concluído ✅", result.updated);

        const hora = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
        setStatus("success", `Salvo às ${hora}`);
        statusEl.innerHTML = `<i class="fas fa-check-circle text-success me-1"></i> Alterações salvas às ${hora}`;
        setTimeout(() => (statusEl.style.display = "none"), 2500);
        showToast(`✅ Alterações salvas às ${hora}`, "success");

        atualizarUltimaModificacao(result.atualizado_em);
        limparMarcador();

        // Atualiza memória local com os valores recém-salvos
        lastSavedData = { ...data };

        // Atualiza histórico se a aba estiver ativa
        const abaHistorico = document.querySelector("#abaHistorico.active");
        if (abaHistorico && typeof refreshHistorico === "function") {
          console.log("[M4] Atualizando histórico em tempo real...");
          refreshHistorico(produtoId);
        }
        // Atualiza contador de histórico global
        if (typeof refreshHistoricoCount === "function") {
          refreshHistoricoCount(produtoId);
        }

      } else {
        console.warn("[M4] Autosave falhou ❌", result.error || result);
        setStatus("error", "Erro ao salvar");
        statusEl.innerHTML = `<i class="fas fa-exclamation-triangle text-warning me-1"></i> Falha ao salvar`;
      }
    } catch (err) {
      console.error("[M4] Erro no autosave:", err);
      setStatus("error", "Erro ao salvar");
      statusEl.innerHTML = `<i class="fas fa-exclamation-circle text-danger me-1"></i> Erro ao salvar`;
    } finally {
      isSaving = false;
    }
  };

  // ============================================================
  // AGENDAMENTO (DEBOUNCE)
  // ============================================================
  const agendarAutosave = () => {
    marcarAbaAlterada();
    if (autosaveTimer) clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(salvarAutomaticamente, delay);
  };

  // ============================================================
  // EVENTOS DE ALTERAÇÃO
  // ============================================================
  form.querySelectorAll("input, select, textarea").forEach(el => {
    el.addEventListener("change", agendarAutosave);
    el.addEventListener("input", agendarAutosave);
  });

  // ============================================================
  // SALVA AO TROCAR DE ABA
  // ============================================================
  document.querySelectorAll("#produtoTabs .nav-link").forEach(tab => {
    tab.addEventListener("click", () => {
      if (!isSaving) salvarAutomaticamente();
    });
  });

  // ============================================================
  // SALVA ANTES DE SAIR DA PÁGINA
  // ============================================================
  window.addEventListener("beforeunload", () => {
    if (!isSaving) salvarAutomaticamente();
  });

})();
