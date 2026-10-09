// ===========================
// MÓDULO: DOCUMENTOS (OCR + CRUD)
// ===========================

document.addEventListener("DOMContentLoaded", () => {
  const btnUploadOCR = document.getElementById("btnUploadOCR");
  const inputUploadOCR = document.getElementById("inputUploadOCR");

  if (btnUploadOCR && inputUploadOCR) {
    // Quando o botão é clicado, dispara o seletor de arquivo
    btnUploadOCR.addEventListener("click", () => inputUploadOCR.click());

    // Quando o usuário seleciona o arquivo, processa via OCR
    inputUploadOCR.addEventListener("change", async (event) => {
      const file = event.target.files[0];
      if (!file) return;

      const csrfInput = document.querySelector('#modalNovoDocumento input[name="csrf_token"]');
      const csrfToken = csrfInput?.value || "";
      if (!csrfToken) {
        exibirToast("Não foi possível validar a sessão. Atualize a página e tente novamente.", "danger");
        inputUploadOCR.value = "";
        return;
      }

      const clienteId = window.location.pathname.split("/")[2]; // extrai o cliente_id da URL
      const formData = new FormData();
      formData.append("arquivo", file);
      formData.append("csrf_token", csrfToken);

      // Feedback visual
      btnUploadOCR.disabled = true;
      btnUploadOCR.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Processando OCR...';

      try {
        const response = await fetch(`/uploads/${clienteId}/documento`, {
          method: "POST",
          headers: { "X-CSRFToken": csrfToken },
          body: formData,
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          const message = data.error || (response.status === 400
            ? "A validação de segurança falhou. Atualize a página e tente novamente."
            : `Não foi possível enviar o arquivo (HTTP ${response.status}).`);
          throw new Error(message);
        }

        // Exibe o modal e só preenche quando estiver visível
        const modalEl = document.getElementById("modalNovoDocumento");
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);

        const onShown = () => {
          // Faz o achatamento *definitivo* dentro do preenchimento também (cobre todos os casos)
          preencherModalNovoDocumento(data);
          // redundância: tenta de novo em 100ms pra evitar corrida residual
          setTimeout(() => preencherModalNovoDocumento(data), 100);
        };

        modalEl.addEventListener("shown.bs.modal", onShown, { once: true });
        modal.show();

        const avisoOcr = data.ocr_warning || data.dados?.erro || "";
        exibirToast(
          avisoOcr || "Dados extraídos. Revise tudo no documento original antes de salvar.",
          avisoOcr ? "warning" : "success"
        );
      } catch (err) {
        exibirToast(err instanceof Error ? err.message : "Falha ao enviar o documento. Tente novamente.", "danger");
      } finally {
        btnUploadOCR.disabled = false;
        btnUploadOCR.innerHTML = '<i class="fas fa-upload me-1"></i> Enviar e Processar Documento (OCR)';
        inputUploadOCR.value = "";
      }
    });
  }
});

// ===========================
// Utils
// ===========================
function getField(modal, nameOrId) {
  return (
    modal.querySelector(`#${nameOrId}`) ||
    modal.querySelector(`[name="${nameOrId}"]`) ||
    null
  );
}

function selectOptionSmart(selectEl, rawValue) {
  if (!selectEl) return false;
  const value = (rawValue ?? "").toString().trim();
  if (!value) return false;

  // 1) value exato
  selectEl.value = value;
  if (selectEl.value === value) return true;

  // 2) value case-insensitive
  const optCI = Array.from(selectEl.options).find(
    (opt) => (opt.value || "").toUpperCase() === value.toUpperCase()
  );
  if (optCI) {
    selectEl.value = optCI.value;
    if (selectEl.value === optCI.value) return true;
  }

  // 3) match pelo texto da opção (contains, CI)
  const optByText = Array.from(selectEl.options).find((opt) =>
    (opt.text || "").toUpperCase().includes(value.toUpperCase())
  );
  if (optByText) {
    selectEl.value = optByText.value;
    if (selectEl.value === optByText.value) return true;
  }

  return false;
}

// Achata objetos aninhados em {dados: {...}} ou {resultado: {...}} recursivamente
function flattenPayload(obj, depth = 0) {
  if (!obj || typeof obj !== "object" || depth > 5) return obj || {};
  if (obj.dados && typeof obj.dados === "object") return flattenPayload(obj.dados, depth + 1);
  if (obj.resultado && typeof obj.resultado === "object") return flattenPayload(obj.resultado, depth + 1);
  return obj;
}

// Normaliza emissor/categoria (heurísticas simples)
function normalizeFields(raw) {
  const out = { ...raw };

  // categoria sempre em maiúsculas
  if (out.categoria && typeof out.categoria === "string") {
    out.categoria = out.categoria.toUpperCase();
  }

  // emissor heurístico
  if (out.emissor && typeof out.emissor === "string") {
    let e = out.emissor.toUpperCase().trim();

    // Mapeamentos comuns
    if (e.includes("DENATRAN")) e = "DETRAN";
    if (e.includes("DETRAN")) e = "DETRAN";
    if (e.includes("SECRETARIA DE SEGURANÇA PÚBLICA") || e.includes("SSP")) e = "SSP";
    if (e.includes("POLÍCIA FEDERAL") || e.includes("POLICIA FEDERAL") || e.includes("SINARM")) e = "SINARM";
    if (e.includes("EXÉRCITO") || e.includes("EXERCITO") || e.includes("SIGMA")) e = "SIGMA";
    if (e.includes("RECEITA")) e = "RECEITA FEDERAL";

    out.emissor = e;
  }

  return out;
}

// ===========================
// Preenche o modal "Novo Documento" com dados do OCR
// ===========================
function preencherModalNovoDocumento(rawData) {
  if (!rawData) return;

  const modal = document.getElementById("modalNovoDocumento");
  if (!modal) return;

  // Achata o payload *aqui* para lidar com qualquer combinação (dados/resultado aninhados)
  let data = flattenPayload(rawData);
  data = normalizeFields(data);

  // 🔧 Novo: tenta também capturar caminho_arquivo no nível raiz
  if (!data.caminho_arquivo) {
    data.caminho_arquivo =
      rawData.caminho_arquivo ||
      rawData.path ||
      rawData.caminho_temp ||
      (rawData.resultado ? rawData.resultado.caminho_arquivo : null) ||
      "";
  }

  const campos = [
    "categoria",
    "emissor",
    "numero_documento",
    "data_emissao",
    "data_validade",
    "observacoes",
  ];

  campos.forEach((campo) => {
    const el = getField(modal, campo);
    if (!el) {
      console.warn(`[OCR] Campo não encontrado no modal: ${campo}`);
      return;
    }

    const valor = data[campo] ?? "";

    if (el.tagName === "SELECT") {
      const ok = selectOptionSmart(el, valor);
      if (!ok) {
        console.warn(`[OCR] Nenhuma opção compatível para o campo ${campo}.`);
      }
      el.dispatchEvent(new Event("change", { bubbles: true }));
    } else if (campo.startsWith("data_") && valor) {
      el.value = converterDataISO(valor);
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    } else {
      el.value = valor;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    }
  });

  // Checkbox de validade indeterminada
  const chk = getField(modal, "validade_indeterminada");
  if (chk) {
    chk.checked = Boolean(data.validade_indeterminada);
    chk.dispatchEvent(new Event("change", { bubbles: true }));
  }

  // Caminho do arquivo (persistência)
  const caminhoInput = getField(modal, "caminho_arquivo");
  if (caminhoInput) {
    caminhoInput.value = data.caminho_arquivo || "";
  } else {
    console.warn("[OCR] Campo 'caminho_arquivo' não encontrado no formulário.");
  }

  // 🔔 dispara evento global (para cache automático)
  if (data.caminho_arquivo) {
    window.dispatchEvent(
      new CustomEvent("OCR_CaminhoGerado", { detail: data.caminho_arquivo })
    );
  }

}

// ===========================
// Conversão de data dd/mm/yyyy → yyyy-mm-dd
// ===========================
function converterDataISO(valor) {
  if (!valor) return "";
  if (valor.includes("-")) return valor;
  const partes = valor.split("/");
  if (partes.length === 3) {
    const [dia, mes, ano] = partes;
    return `${ano}-${mes.padStart(2, "0")}-${dia.padStart(2, "0")}`;
  }
  return valor;
}

// ===========================
// Toasts rápidos (sucesso / erro)
// ===========================
function exibirToast(mensagem, tipo = "info") {
  const toast = document.createElement("div");
  toast.className = `toast align-items-center text-bg-${tipo} border-0 show position-fixed bottom-0 end-0 m-3`;
  toast.setAttribute("role", "alert");
  toast.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${mensagem}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>
  `;
  toast.querySelector(".toast-body").textContent = mensagem;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ===============================
// EDIÇÃO DINÂMICA DE DOCUMENTOS
// ===============================
document.addEventListener("DOMContentLoaded", () => {
  const modalElement = document.getElementById("modalEditarDocumentoDinamico");
  const modalBody = document.getElementById("modalEditarConteudo");
  if (!modalElement || !modalBody) return;

  const modal = new bootstrap.Modal(modalElement);

  document.querySelectorAll(".btn-outline-primary[data-doc-id]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const clienteId = window.location.pathname.split("/")[2];
      const docId = btn.getAttribute("data-doc-id");

      modalBody.innerHTML = `
        <div class="text-center py-5 text-muted">
          <i class="fas fa-spinner fa-spin me-2"></i>Carregando formulário...
        </div>`;
      modal.show();

      try {
        const url = `/clientes/${clienteId}/documentos/${docId}/editar`;
        const response = await fetch(url);

        if (!response.ok) throw new Error(`Erro ${response.status}: Falha ao carregar formulário.`);

        const html = await response.text();
        modalBody.innerHTML = html;
      } catch (err) {
        modalBody.innerHTML = `
          <div class="text-center text-danger py-5">
            <i class="fas fa-exclamation-triangle me-2"></i>
            Erro ao carregar formulário de edição.
          </div>`;
      }
    });
  });
});

// ===============================
// FIX: garante que o campo caminho_arquivo exista e seja enviado
// ===============================
document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("modalNovoDocumento");
  if (!modal) return;

  const form = modal.querySelector("form");
  if (!form) return;

  // Ao abrir o modal, se não existir o campo hidden, cria
  modal.addEventListener("shown.bs.modal", () => {
    let hidden = form.querySelector("#caminho_arquivo");
    if (!hidden) {
      hidden = document.createElement("input");
      hidden.type = "hidden";
      hidden.name = "caminho_arquivo";
      hidden.id = "caminho_arquivo";
      form.appendChild(hidden);
    }

    // Se o OCR já preencheu, mantém o valor; senão, tenta recuperar
    const currentVal = hidden.value?.trim();
    if (!currentVal) {
      const temp = window?.ultimoCaminhoOCR || "";
      if (temp) {
        hidden.value = temp;
      }
    }
  });

  // Captura o caminho logo após o OCR processar (para cache temporário)
  window.addEventListener("OCR_CaminhoGerado", (e) => {
    if (!e.detail) return;
    window.ultimoCaminhoOCR = e.detail;
    const hidden = form.querySelector("#caminho_arquivo");
    if (hidden) hidden.value = e.detail;
  });
});


// ===============================
// FIX: PREVENIR PISCADAS DE MODAL
// ===============================
document.addEventListener("DOMContentLoaded", () => {
  const modalElement = document.getElementById("modalEditarDocumentoDinamico");
  if (!modalElement) return;

  const adjustBackdrop = () => {
    const backdrops = document.querySelectorAll(".modal-backdrop.show");
    if (backdrops.length > 1) {
      for (let i = 0; i < backdrops.length - 1; i++) {
        backdrops[i].remove();
      }
    }
    modalElement.style.zIndex = "1065";
  };

  modalElement.addEventListener("shown.bs.modal", () => {
    setTimeout(adjustBackdrop, 100);
  });

  modalElement.addEventListener("hide.bs.modal", () => {
    adjustBackdrop();
  });
});
