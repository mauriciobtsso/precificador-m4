// ===========================================================
// MÓDULO: PRODUTOS_FORM.JS — Com Suporte a Promoção (Versão Corrigida - Módulo)
// ===========================================================

(() => {
  console.log("[M4] produtos_form.js carregado (v-promo)");

  const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  const el = (id) => document.getElementById(id);
  
  // Variáveis globais dentro do módulo para as instâncias do AutoNumeric
  let anFornecedor, anLucroAlvo, anPrecoFinal, anFrete, anIPI, anPromoPreco;
  
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


// ============================================================
  // ESPECIFICAÇÕES DINÂMICAS (JSON)
  // ============================================================
  function addEspecificacao(chave = "", valor = "") {
    const container = document.getElementById("container-especificacoes");
    if (!container) return;

    const div = document.createElement("div");
    div.className = "row g-2 mb-2 especificacao-row animate__animated animate__fadeIn";
    div.innerHTML = `
      <div class="col-5">
        <input type="text" class="form-control form-control-sm espec-chave" placeholder="Atributo" value="${chave}">
      </div>
      <div class="col-6">
        <input type="text" class="form-control form-control-sm espec-valor" placeholder="Valor" value="${valor}">
      </div>
      <div class="col-1 text-end">
        <button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="this.closest('.especificacao-row').remove(); window.ProdutosForm.serializarEspecificacoes();">
          <i class="fas fa-times"></i>
        </button>
      </div>
    `;
    container.appendChild(div);

    // Listeners para atualizar o JSON oculto sempre que digitar
    div.querySelectorAll('input').forEach(input => {
      input.addEventListener('input', debounce(serializarEspecificacoes, 500));
    });
  }

  function serializarEspecificacoes() {
    const rows = document.querySelectorAll(".especificacao-row");
    const data = {};
    rows.forEach(row => {
      const chave = row.querySelector(".espec-chave").value.trim();
      const valor = row.querySelector(".espec-valor").value.trim();
      if (chave) {
        data[chave] = valor;
      }
    });
    const jsonInput = document.getElementById("in_especificacoes_tecnicas_json");
    if (jsonInput) {
      jsonInput.value = JSON.stringify(data);
      // Notifica o Autosave que o campo oculto mudou
      jsonInput.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  function initEspecificacoes() {
    // Adiciona listeners nas linhas já renderizadas pelo Jinja2
    document.querySelectorAll(".especificacao-row input").forEach(input => {
      input.addEventListener('input', debounce(serializarEspecificacoes, 500));
    });
    serializarEspecificacoes(); // Primeira carga
  }

// ============================================================
  // SUMMERNOTE: Inicialização segura para aba Ecommerce (FIX DEFINITIVO)
  // ============================================================
  function syncSummernote() {
    const editorId = "editor_loja_m4";
    const $editor = $("#" + editorId);
    if ($editor.length && $editor.data("summernote")) {
        const contents = $editor.summernote("code");
        $editor.val(contents);
        console.log("[M4] Summernote: Sincronização manual realizada antes do envio.");
    }
  }

  function initSummernoteEcommerce() {
    const editorId = "editor_loja_m4";
    const textarea = document.getElementById(editorId);

    if (!textarea) {
      console.warn("[M4] Summernote: textarea #editor_loja_m4 não encontrado.");
      return;
    }

    // Garante jQuery
    if (typeof window.$ === "undefined") {
      console.error("[M4] Summernote: jQuery não está carregado.");
      return;
    }

    // Garante plugin
    if (!$.fn || typeof $.fn.summernote === "undefined") {
      console.error("[M4] Summernote: plugin não está carregado ($.fn.summernote undefined).");
      return;
    }

    const $editor = $("#" + editorId);

    // Se já existe instância mas o DOM ficou bugado, reinicia
    const hasEditorUI = $editor.next().hasClass("note-editor");
    const isSummernoteActive = !!$editor.data("summernote");

    // Caso exista UI mas data sumiu (bug clássico de renderização em abas)
    if (hasEditorUI && !isSummernoteActive) {
      console.warn("[M4] Summernote: UI existe mas instância não. Resetando...");
      try { $editor.summernote("destroy"); } catch (_) {}
    }

    // Caso já esteja inicializado corretamente
    if ($editor.data("summernote")) {
      // Força refresh visual ao mostrar aba para evitar que suma o texto
      setTimeout(() => {
        try {
          const current = $editor.summernote("code");
          $editor.summernote("code", current);
        } catch (_) {}
      }, 80);
      return;
    }

    // Se tinha UI antiga órfã, destrói para não duplicar na tela
    if ($editor.next().hasClass("note-editor")) {
      try {
        $editor.summernote("destroy");
      } catch (e) {
        console.warn("[M4] Summernote: falha ao destruir instância antiga:", e);
      }
    }

    console.log("[M4] Summernote: inicializando agora...");

    $editor.summernote({
      height: 450,
      lang: "pt-BR",
      placeholder: "Utilize as ferramentas acima para formatar negritos, listas, tabelas e inserir links...",
      toolbar: [
        ["style", ["style"]],
        ["font", ["bold", "underline", "clear"]],
        ["color", ["color"]],
        ["para", ["ul", "ol", "paragraph"]],
        ["table", ["table"]],
        ["insert", ["link", "picture", "video"]],
        ["view", ["fullscreen", "codeview"]]
      ],
      callbacks: {
        onChange: function(contents) {
          // Sincronização imediata: mantém o textarea real com o valor do editor visual
          $editor.val(contents);
          
          // Dispara eventos para que o Autosave e outros scripts percebam a mudança
          textarea.dispatchEvent(new Event("change", { bubbles: true }));
          textarea.dispatchEvent(new Event("input", { bubbles: true }));
        },
        onBlurCodeview: function() {
          // Garante que se o usuário editar no modo código (HTML puro) e sair, o valor seja salvo
          $editor.val($editor.summernote("code"));
        },
        onInit: function() {
          console.log("[M4] Summernote: renderizado com sucesso ✅");

          // Hack de correção de altura para containers que iniciam ocultos (como abas do Bootstrap)
          setTimeout(() => {
            try {
              const current = $editor.summernote("code");
              $editor.summernote("code", current);
            } catch (_) {}
          }, 120);
        }
      }
    });
  }

  // ============================================================
  // FOTO: galeria com upload múltiplo e foto principal
  // ============================================================
  function initFotoProduto() {
    const btn = el("btnSelecionarFoto");
    const input = el("inputFotoProduto");
    const grid = el("galeriaProdutoGrid");
    const empty = el("galeriaProdutoVazia");
    const overlay = el("fotoProdutoOverlay");
    const hidden = el("inputFotosProduto");
    const legacy = el("inputFotoUrl");
    if (!btn || !input || !grid || !hidden) return;
    if (grid.dataset.bound === "1") return;
    grid.dataset.bound = "1";

    let fotos = [];
    try { fotos = JSON.parse(el("fotosProdutoIniciais")?.textContent || "[]"); } catch (_) {}
    if (!fotos.length && legacy?.value) fotos = [{ url: legacy.value, principal: true }];
    fotos = fotos.filter(f => f && f.url).map((f, index) => ({
      url: f.url, principal: !!f.principal || (!fotos.some(x => x.principal) && index === 0),
      preview: f.url
    }));

    const sync = () => {
      if (fotos.length && !fotos.some(f => f.principal)) fotos[0].principal = true;
      hidden.value = JSON.stringify(fotos.map(f => ({ url: f.url, principal: !!f.principal })));
      if (legacy) legacy.value = fotos.find(f => f.principal)?.url || "";
      empty.classList.toggle("d-none", fotos.length > 0);
      grid.innerHTML = fotos.map((foto, index) => `
        <div class="col">
          <div class="produto-foto-thumb ${foto.principal ? "is-principal" : ""}">
            <img src="${foto.preview || foto.url}" alt="Foto ${index + 1}" loading="lazy">
            <button type="button" class="btn btn-sm btn-danger produto-foto-remove" data-index="${index}" title="Remover">
              <i class="fas fa-times"></i>
            </button>
            <label class="produto-foto-primary" title="Definir como principal">
              <input type="radio" name="foto_principal_ui" value="${index}" ${foto.principal ? "checked" : ""}>
              <span><i class="fas fa-star"></i> Principal</span>
            </label>
          </div>
        </div>`).join("");
      grid.querySelectorAll(".produto-foto-remove").forEach(b => b.addEventListener("click", () => {
        const removed = fotos.splice(Number(b.dataset.index), 1)[0];
        if (removed?.principal && fotos.length) fotos[0].principal = true;
        sync();
      }));
      grid.querySelectorAll("input[name=foto_principal_ui]").forEach(radio => radio.addEventListener("change", () => {
        fotos.forEach((f, i) => f.principal = i === Number(radio.value));
        sync();
      }));
    };

    btn.addEventListener("click", () => input.click());
    input.addEventListener("change", async () => {
      const arquivos = Array.from(input.files || []);
      if (!arquivos.length) return;
      overlay?.classList.remove("d-none");
      try {
        for (const file of arquivos) {
          const fd = new FormData();
          fd.append("file", file);
          fd.append("produto_id", getProdutoId() || "novo");
          const response = await fetch("/produtos/api/upload_foto", { method: "POST", body: fd });
          const data = await response.json();
          if (!response.ok || !data.success || !data.foto_url) throw new Error(data.error || "Falha no upload");
          const preview = URL.createObjectURL(file);
          fotos.push({ url: data.foto_url, preview, principal: fotos.length === 0 });
        }
        sync();
        input.value = "";
      } catch (error) {
        console.error("[M4] Erro no upload da galeria:", error);
        alert("Não foi possível enviar uma das fotos. Tente novamente.");
      } finally { overlay?.classList.add("d-none"); }
    });
    sync();
  }

  // ============================================================
  // VÍDEO: galeria com upload múltiplo e títulos editáveis
  // ============================================================
  function initVideoProduto() {
    const btn = el("btnSelecionarVideo");
    const input = el("inputVideoProduto");
    const grid = el("galeriaVideoProdutoGrid");
    const empty = el("galeriaVideoVazia");
    const overlay = el("videoProdutoOverlay");
    const hidden = el("inputVideosProduto");
    if (!btn || !input || !grid || !hidden) return;
    if (grid.dataset.bound === "1") return;
    grid.dataset.bound = "1";
    let videos = [];
    try { videos = JSON.parse(el("videosProdutoIniciais")?.textContent || "[]"); } catch (_) {}
    videos = videos.filter(v => v && v.url).map(v => ({ url: v.url, titulo: v.titulo || "", preview: v.url }));
    const escapeAttr = (value) => String(value || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const sync = () => {
      hidden.value = JSON.stringify(videos.map(v => ({ url: v.url, titulo: (v.titulo || "").trim() })));
      empty?.classList.toggle("d-none", videos.length > 0);
      grid.innerHTML = videos.map((video, index) => `
        <div class="col">
          <div class="border rounded bg-white p-2 position-relative">
            <video src="${escapeAttr(video.preview || video.url)}" class="w-100 rounded" style="height:120px;object-fit:cover" controls muted preload="metadata"></video>
            <button type="button" class="btn btn-sm btn-danger position-absolute top-0 end-0 m-1 produto-video-remove" data-index="${index}" title="Remover vídeo"><i class="fas fa-times"></i></button>
            <input type="text" class="form-control form-control-sm mt-2 produto-video-title" data-index="${index}" value="${escapeAttr(video.titulo)}" placeholder="Título opcional do vídeo" maxlength="180">
          </div>
        </div>`).join("");
      grid.querySelectorAll(".produto-video-remove").forEach(b => b.addEventListener("click", () => {
        const removed = videos.splice(Number(b.dataset.index), 1)[0];
        if (removed?.preview?.startsWith("blob:")) URL.revokeObjectURL(removed.preview);
        sync();
      }));
      grid.querySelectorAll(".produto-video-title").forEach(field => field.addEventListener("input", () => {
        videos[Number(field.dataset.index)].titulo = field.value;
        hidden.value = JSON.stringify(videos.map(v => ({ url: v.url, titulo: (v.titulo || "").trim() })));
      }));
    };
    btn.addEventListener("click", () => input.click());
    input.addEventListener("change", async () => {
      const arquivos = Array.from(input.files || []);
      if (!arquivos.length) return;
      const tiposAceitos = ["video/mp4", "video/webm", "video/quicktime"];
      if (arquivos.some(file => file.size > 100 * 1024 * 1024 || !tiposAceitos.includes(file.type))) {
        alert("Use vídeos MP4, WebM ou MOV com no máximo 100 MB cada.");
        input.value = "";
        return;
      }
      overlay?.classList.remove("d-none");
      try {
        for (const file of arquivos) {
          const fd = new FormData();
          fd.append("file", file);
          fd.append("produto_id", getProdutoId() || "novo");
          const response = await fetch("/produtos/api/upload_video", { method: "POST", body: fd });
          const data = await response.json();
          if (!response.ok || !data.success || !data.video_url) throw new Error(data.error || "Falha no upload");
          videos.push({ url: data.video_url, titulo: file.name.replace(/\.[^/.]+$/, ""), preview: URL.createObjectURL(file) });
        }
        sync();
        input.value = "";
      } catch (error) {
        console.error("[M4] Erro no upload da galeria de vídeos:", error);
        alert(error.message || "Não foi possível enviar um dos vídeos. Tente novamente.");
      } finally { overlay?.classList.add("d-none"); }
    });
    sync();
  }

  // ============================================================
  // TOUR 360: frames ordenados com pré-visualização e remoção
  // ============================================================
  function initTour360Produto() {
    const btn = el("btnSelecionarTour360");
    const input = el("inputTour360Produto");
    const preview = el("tour360ProdutoPreview");
    const empty = el("tour360ProdutoVazio");
    const hidden = el("inputTour360ProdutoJson");
    if (!btn || !input || !preview || !hidden) return;
    if (preview.dataset.bound === "1") return;
    preview.dataset.bound = "1";
    let config = { titulo: "", ativo: true, frames: [] };
    try { config = { ...config, ...JSON.parse(el("tour360ProdutoInicial")?.textContent || "{}") }; } catch (_) {}
    config.frames = (config.frames || []).map(url => typeof url === "string" ? ({ url, preview: url }) : url).filter(frame => frame?.url);
    const sync = () => {
      hidden.value = JSON.stringify({ titulo: config.titulo || "", ativo: config.ativo !== false, frames: config.frames.map(frame => ({ url: frame.url })) });
      empty?.classList.toggle("d-none", config.frames.length > 0);
      preview.innerHTML = config.frames.map((frame, index) => `
        <div class="col">
          <div class="border rounded bg-white p-1 position-relative">
            <img src="${String(frame.preview || frame.url).replace(/"/g, "&quot;")}" class="w-100 rounded" style="height:72px;object-fit:cover" alt="Frame ${index + 1}" loading="lazy">
            <div class="d-flex justify-content-center gap-1 mt-1">
              <button type="button" class="btn btn-sm btn-light tour360-move" data-index="${index}" data-direction="-1" ${index === 0 ? "disabled" : ""} aria-label="Mover frame para trás"><i class="fas fa-chevron-left"></i></button>
              <span class="small text-muted align-self-center">${index + 1}</span>
              <button type="button" class="btn btn-sm btn-light tour360-move" data-index="${index}" data-direction="1" ${index === config.frames.length - 1 ? "disabled" : ""} aria-label="Mover frame para frente"><i class="fas fa-chevron-right"></i></button>
            </div>
            <button type="button" class="btn btn-sm btn-danger position-absolute top-0 end-0 m-1 tour360-remove" data-index="${index}" title="Remover frame"><i class="fas fa-times"></i></button>
          </div>
        </div>`).join("");
      preview.querySelectorAll(".tour360-remove").forEach(button => button.addEventListener("click", () => {
        const removed = config.frames.splice(Number(button.dataset.index), 1)[0];
        if (removed?.preview?.startsWith("blob:")) URL.revokeObjectURL(removed.preview);
        sync();
      }));
      preview.querySelectorAll(".tour360-move").forEach(button => button.addEventListener("click", () => {
        const index = Number(button.dataset.index);
        const target = index + Number(button.dataset.direction);
        if (target < 0 || target >= config.frames.length) return;
        [config.frames[index], config.frames[target]] = [config.frames[target], config.frames[index]];
        sync();
      }));
    };
    btn.addEventListener("click", () => input.click());
    input.addEventListener("change", async () => {
      const arquivos = Array.from(input.files || []);
      if (!arquivos.length) return;
      const tiposAceitos = ["image/jpeg", "image/png", "image/webp"];
      if (arquivos.some(file => file.size > 15 * 1024 * 1024 || !tiposAceitos.includes(file.type))) {
        alert("Use frames JPG, PNG ou WebP com no máximo 15 MB cada.");
        input.value = "";
        return;
      }
      btn.disabled = true;
      try {
        for (const file of arquivos) {
          const fd = new FormData();
          fd.append("file", file);
          fd.append("produto_id", getProdutoId() || "novo");
          const response = await fetch("/produtos/api/upload_tour360_frame", { method: "POST", body: fd });
          const data = await response.json();
          if (!response.ok || !data.success || !data.frame_url) throw new Error(data.error || "Falha no upload");
          config.frames.push({ url: data.frame_url, preview: URL.createObjectURL(file) });
        }
        sync();
        input.value = "";
      } catch (error) {
        console.error("[M4] Erro no upload do tour 360:", error);
        alert(error.message || "Não foi possível enviar um dos frames.");
      } finally { btn.disabled = false; }
    });
    sync();
  }

  function initAcessoriosProduto() {
    const select = el("selectAcessoriosProduto");
    const hidden = el("inputAcessoriosProduto");
    if (!select || !hidden || select.dataset.bound === "1") return;
    select.dataset.bound = "1";
    const sync = () => { hidden.value = JSON.stringify(Array.from(select.selectedOptions).map(option => Number(option.value)).filter(Number.isFinite)); };
    select.addEventListener("change", sync);
    sync();
  }


  // ============================================================
  // Máscara dinâmica do IPI (Manutenção da Lógica)
  // ============================================================
  const ipiInput = document.getElementById("in_ipi");
  const ipiTipoSelect = document.getElementById("in_ipi_tipo");

  function initIpiMask(forceClear = false) {
    if (!ipiInput || !ipiTipoSelect) return;

    let valorAtual = 0;
    if (anIPI && AutoNumeric.isManagedByAutoNumeric(ipiInput)) {
        valorAtual = anIPI.getNumber();
    } else {
        valorAtual = num("in_ipi");
    }
    if (forceClear) valorAtual = 0;

    if (anIPI && AutoNumeric.isManagedByAutoNumeric(ipiInput)) {
        anIPI.remove();
    }

    const tipoNovo = ipiTipoSelect.value;
    const ipiOpts = {
        digitGroupSeparator: ".",
        decimalCharacter: ",",
        decimalPlaces: 2,
        modifyValueOnWheel: false,
        emptyInputBehavior: "zero",
        unformatOnSubmit: true
    };

    if (tipoNovo === "fixo" || tipoNovo === "R$") {
      anIPI = new AutoNumeric(ipiInput, { ...ipiOpts, currencySymbol: "R$ " });
    } else {
      anIPI = new AutoNumeric(ipiInput, { ...ipiOpts, suffixText: " %", maximumValue: "1000", minimumValue: "0" });
    }

    anIPI.set(valorAtual);
    ipiInput.dataset.maskType = tipoNovo;
  }
  
  // Listener para IPI Tipo
  if (ipiTipoSelect) {
      ipiTipoSelect.addEventListener("change", () => {
        initIpiMask(true); 
        recalcular();
      });
  }

  // ============================================================
  // INICIALIZAÇÃO DE MÁSCARAS (Função unificada para init e reinit)
  // ============================================================
  function initMasks() {
    if (typeof AutoNumeric === "undefined") {
      console.warn("[M4] AutoNumeric não encontrado. Máscaras desativadas.");
      return;
    }
    
    // Remove instâncias AutoNumeric existentes antes de recriar
    const elementsToRemove = document.querySelectorAll('.autonumeric-managed');
    elementsToRemove.forEach(el => {
        if (AutoNumeric.isManagedByAutoNumeric(el)) {
            try { AutoNumeric.getAutoNumericElement(el).remove(); } catch (e) { /* silent fail */ }
        }
    });

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
    const createMoney = (selector) => {
      const element = document.querySelector(selector);
      if (!element) return null;
      element.classList.add('autonumeric-managed');
      const an = new AutoNumeric(selector, brlOpts);
      if (element.value && element.value.trim() !== "") {
          an.set(element.value);
      }
      return an;
    };

    // Inicializa campos principais (Restaurando IDs originais)
    anFornecedor = createMoney("#in_preco_fornecedor");
    anLucroAlvo  = createMoney("#in_lucro_alvo");
    anPrecoFinal = createMoney("#in_preco_final");
    anFrete      = createMoney("#in_frete");
    anPromoPreco = createMoney("#in_promo_preco");

    // Campos percentuais simples
    ["in_margem", "in_difal", "in_imposto_venda", "in_desconto"].forEach((id) => {
      const selector = `#${id}`;
      const $i = el(id);
      if ($i) {
        try { 
            $i.setAttribute("type", "text"); 
            $i.classList.add('autonumeric-managed');
            new AutoNumeric(selector, percOpts);
        } catch (_) {} 
      }
    });

    // Inicializa IPI (Dinâmico)
    initIpiMask(false);
    
    // Listeners para AutoNumeric
    document.removeEventListener("autoNumeric:rawValueModified", recalcularListener);
    document.addEventListener("autoNumeric:rawValueModified", recalcularListener);
  }

  // Listener principal do AutoNumeric, para evitar duplicação de eventos
  function recalcularListener(e) {
    if (["in_preco_fornecedor", "in_lucro_alvo", "in_preco_final", "in_frete", "in_ipi", "in_promo_preco"].includes(e.target.id)) {
      recalcular();
    }
  }


  // =========================================
  // LÓGICA FINANCEIRA (Com Promoção)
  // =========================================
  function recalcular() {
    try {
      // 1. Determina Preço Base (Promoção vs Normal)
      let precoBase = getAN(anFornecedor);
      
      const promoAtiva = el("in_promo_ativada")?.checked;
      const promoPreco = getAN(anPromoPreco);
      const dataInicio = el("in_promo_inicio")?.value;
      const dataFim = el("in_promo_fim")?.value;

      let usandoPromo = false;
      if (promoAtiva && promoPreco > 0) {
          const agora = new Date();
          const dtIni = dataInicio ? new Date(dataInicio) : null;
          const dtFim = dataFim ? new Date(dataFim) : null;
          
          if ((!dtIni || agora >= dtIni) && (!dtFim || agora <= dtFim)) {
              precoBase = promoPreco;
              usandoPromo = true;
          }
      }

      // Feedback visual no campo de fornecedor
      const lblFornecedor = el("in_preco_fornecedor");
      const promoPrecoEl = el("in_promo_preco");
      if(lblFornecedor) {
          if(usandoPromo) {
              lblFornecedor.classList.add("text-decoration-line-through", "text-muted");
              if(promoPrecoEl) promoPrecoEl.classList.add("border-success", "text-success", "fw-bold");
          } else {
              lblFornecedor.classList.remove("text-decoration-line-through", "text-muted");
              if(promoPrecoEl) promoPrecoEl.classList.remove("border-success", "text-success", "fw-bold");
          }
      }

      // 2. Lê outros valores
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

      // 3. Cálculos
      const valorComDesconto = precoBase * (1 - descFornecedor / 100);
      
      if (el("out_desconto")) el("out_desconto").textContent = brl.format(valorComDesconto || 0);
      if (el("out_frete")) el("out_frete").textContent = brl.format(frete || 0);

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
      const baseDifal = Math.max(base - valorIPI + frete, 0);
      const valorDifal = baseDifal * (difal / 100);
      
      // Custo Total
      const custoTotal = base + valorDifal + frete;

      // Sugestão de Preço
      if (!(precoFinal > 0)) {
        if (lucroAlvo > 0) {
          precoFinal = (custoTotal + lucroAlvo) / (1 - impostoVenda / 100);
        } else if (margem > 0) {
          precoFinal = custoTotal / (1 - margem / 100);
        } else {
          precoFinal = custoTotal;
        }
      }

      // Resultados Finais
      const impostoVendaValor = precoFinal * (impostoVenda / 100);
      const lucroLiquido = precoFinal - custoTotal - impostoVendaValor;

      // 4. Exibe na Tela (Resumo)
      const setVal = (id, val) => { const elem = el(id); if (elem) elem.value = brl.format(isFinite(val) ? val : 0); };
      setVal("out_custo_total", custoTotal);
      setVal("out_preco_a_vista", precoFinal);
      setVal("out_lucro_liquido", lucroLiquido);

      if (el("out_ipi")) el("out_ipi").textContent = brl.format(valorIPI || 0);
      if (el("out_difal")) el("out_difal").textContent = brl.format(valorDifal || 0);
      if (el("out_imposto")) el("out_imposto").textContent = brl.format(impostoVendaValor || 0);

      atualizarResumoVisual(lucroLiquido);

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
  // Listeners para campos não-AutoNumeric
  // =========================================
  const debounce = (fn, delay = 200) => {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); };
  };

  function setupStaticListeners() {
    // Inputs que disparam recalculo (além dos de AutoNumeric)
    const idsTriggers = [
        "in_desconto", "in_margem", "in_imposto_venda", "in_difal", "in_ipi", 
        "in_promo_ativada", "in_promo_inicio", "in_promo_fim" 
    ];

    idsTriggers.forEach((id) => {
      const input = el(id);
      if (input) input.addEventListener("input", debounce(recalcular, 300));
      if (input && input.type === 'checkbox') input.addEventListener("change", recalcular);
    });
  }

  function corrigirAlturaAbas() {
    const tabs = document.querySelectorAll("#produtoTabs .nav-link");
    tabs.forEach(t => t.style.minWidth = "100px");
  }

  // =========================================
  // EXPORTAÇÃO DO MÓDULO (Para atender a produto_form.html)
  // =========================================
  const ProdutosForm = {
    // Método principal chamado em window.load
    init: function() {
      initFotoProduto(); 
      initVideoProduto();
      initTour360Produto();
      initAcessoriosProduto();
      initMasks(); 
      setupStaticListeners();
      corrigirAlturaAbas();
      initEspecificacoes();

      // Se abrir direto na aba Ecommerce (ex: url com hash ou cache)
      setTimeout(() => {
        if (document.querySelector("#abaEcommerce.active")) {
          initSummernoteEcommerce();
        }
      }, 500);

      setTimeout(() => {
        recalcular();
        console.info("[M4] Inicialização Completa e Recalcular inicial OK.");
      }, 800);
    },
    
    // Método chamado ao trocar de aba
    reinitMasks: initMasks,
    refreshResumo: recalcular,
    
    addEspecificacao: addEspecificacao,
    serializarEspecificacoes: serializarEspecificacoes,

    // NOVO: exposto para o produto_form.html chamar
    initSummernoteEcommerce: initSummernoteEcommerce,
  };
  
  window.ProdutosForm = ProdutosForm; 
  window.recalcularProduto = recalcular;

})();
