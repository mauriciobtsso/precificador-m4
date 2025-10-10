// =================================================================
// ARMAS - JS (Versão Final com Padronização de Calibre por Manus)
// Adiciona regras de negócio para padronizar calibres comuns.
// VERSÃO COMPLETA E SEM OMISSÕES
// =================================================================

(() => {
  const log = (...a) => console.log("[ARMAS]", ...a);

  // ============
  // Utilitários
  // ============
  const $id = (id) => document.getElementById(id);

  function setValById(id, val) {
    const el = $id(id);
    if (!el) return;
    const v = val ?? "";
    el.value = v;
    try { el.setAttribute("value", v); } catch (_) {}
  }

  function setSelectMatchById(id, target) {
    const el = $id(id);
    if (!el) return;

    const wanted = (target ?? "").toString().trim();
    if (!wanted) { el.value = ""; return; }

    const wantedLower = wanted.toLowerCase();
    const byValue = Array.from(el.options).find(
      (opt) => (opt.value || "").toLowerCase() === wantedLower
    );
    if (byValue) { el.value = byValue.value; return; }

    const byLabel = Array.from(el.options).find(
      (opt) => (opt.text || "").toLowerCase() === wantedLower
    );
    if (byLabel) { el.value = byLabel.value; return; }

    el.value = "";
  }

  // ============
  // Normalização APRIMORADA
  // ============
  function mapEmissor(e) {
    const t = (e || "").toUpperCase();
    if (t.includes("EXÉRCITO") || t.includes("MILITAR") || t.includes("BOMBEIROS")) return "sigma";
    if (t.includes("FEDERAL") || t.includes("JUSTIÇA")) return "sinarm";
    return (e || "").toLowerCase();
  }

  function onlyDigits(str) {
    return (str || "").replace(/\D+/g, "");
  }

  function normalizeDados(json) {
    const d = json || {};

    // --- Valores brutos do LLM ---
    let serie = (d.numero_serie || "").toString().trim();
    let modelo = (d.modelo || "").toString().trim();
    let calibre = (d.calibre || "").toString().trim();
    let marca = (d.marca || "").toString().trim();

    // --- Lógica de Parsing Avançada ---

    // 1. Corrige a inversão de Modelo e Número de Série
    const separadorSerie = /Nº Da Arma:/i;
    if (separadorSerie.test(modelo)) {
        log("Padrão 'Nº Da Arma' detectado no modelo. Limpando e validando...");
        const partes = modelo.split(separadorSerie);
        const modeloLimpo = partes[0].trim();
        const serieExtraida = partes[1].trim();
        modelo = modeloLimpo;
        if (serieExtraida) {
            serie = serieExtraida;
        }
    }

    // 2. Limpa o campo Calibre de informações extras
    const separadorCapacidade = /Capacidade de Tiros/i;
    if (separadorCapacidade.test(calibre)) {
        log("Limpando 'Capacidade de Tiros' do campo Calibre.");
        calibre = calibre.split(separadorCapacidade)[0].trim();
    }

    // 3. Limpa o campo Marca, removendo os tipos de arma
    const tiposDeArma = ["PISTOLA", "REVÓLVER", "REVOLVER", "ESPINGARDA", "CARABINA", "FUZIL"];
    let marcaLimpa = marca;
    for (const tipo of tiposDeArma) {
        const regex = new RegExp(`^${tipo}\\s+`, "i");
        if (regex.test(marcaLimpa)) {
            log(`Limpando tipo '${tipo}' do campo Marca.`);
            marcaLimpa = marcaLimpa.replace(regex, "").trim();
            break;
        }
    }
    marca = marcaLimpa;

    // 4. Padroniza (cria aliases para) Marcas conhecidas
    const marcaUpper = marca.toUpperCase();
    if (marcaUpper.includes("FORJAS TAURUS") || marcaUpper.includes("TAURUS ARMAS")) {
        log("Padronizando marca para TAURUS.");
        marca = "TAURUS";
    } else if (marcaUpper.includes("COMPANHIA BRASILEIRA DE CARTUCHOS")) {
        log("Padronizando marca para CBC.");
        marca = "CBC";
    }

    // ✅ 5. Padroniza (cria aliases para) Calibres comuns
    const calibreUpper = calibre.toUpperCase();
    if (calibreUpper.includes("9X19") || calibreUpper.includes("9MM") || calibreUpper.includes("9 MM")) {
        log(`Padronizando calibre '${calibre}' para '9x19'.`);
        calibre = "9x19";
    }
    // Adicionar outras regras de calibre aqui no futuro (ex: .380, .40, etc.)

    // --- Fim da Lógica de Parsing ---

    const textoCompleto = `${d.marca || ""} ${modelo} ${d.tipo || ""}`.toUpperCase();

    // --- Lógica do Sigma (já correta) ---
    let sigmaFinal = "";
    const sigmaBruto = (d.numero_sigma || "").toString().trim();
    let candidatoSigma = sigmaBruto;
    if (!candidatoSigma) {
        candidatoSigma = (d.numero_documento || "").toString().trim();
    }
    if (serie && candidatoSigma.includes(serie)) {
        candidatoSigma = candidatoSigma.replace(serie, "").trim();
    }
    const sigmaLimpo = onlyDigits(candidatoSigma);
    if (sigmaLimpo && sigmaLimpo !== onlyDigits(serie)) {
        sigmaFinal = sigmaLimpo;
    } else if (onlyDigits(sigmaBruto) && onlyDigits(sigmaBruto) !== onlyDigits(serie)) {
        sigmaFinal = onlyDigits(sigmaBruto);
    }
    // --- Fim da lógica do Sigma ---

    // --- Lógica de Inferência ---
    let tipoInferido = d.tipo || "";
    if (!tipoInferido) {
        if (textoCompleto.includes("PISTOLA")) tipoInferido = "Pistola";
        else if (textoCompleto.includes("REVÓLVER") || textoCompleto.includes("REVOLVER")) tipoInferido = "Revólver";
        else if (textoCompleto.includes("ESPINGARDA")) tipoInferido = "Espingarda";
        else if (textoCompleto.includes("CARABINA") || textoCompleto.includes("FUZIL")) tipoInferido = "Carabina";
    }

    let funcInferido = d.funcionamento || "";
    if (!funcInferido) {
        log(`Inferindo funcionamento a partir do tipo: '${tipoInferido}'`);
        const tipoLower = tipoInferido.toLowerCase();
        if (tipoLower === "pistola") {
            funcInferido = "Semi-automática";
        } else if (tipoLower === "revólver") {
            funcInferido = "Repetição";
        }
    }
    // --- Fim da Lógica de Inferência ---

    // --- Conversão final para MAIÚSCULAS ---
    return {
      tipo: tipoInferido,
      funcionamento: funcInferido,
      marca: marca.toUpperCase(),
      modelo: modelo.toUpperCase(),
      calibre: calibre.toUpperCase(),
      numero_serie: serie.toUpperCase(),
      numero_sigma: sigmaFinal,
      emissor_craf: mapEmissor(d.emissor_craf || d.emissor),
      categoria_adquirente: (d.categoria_adquirente || "").toUpperCase(),
      data_validade_craf: d.data_validade_craf || d.data_validade || "",
      validade_indeterminada: !!d.validade_indeterminada,
      caminho_craf: d.caminho_craf || d.caminho || "",
      nome_original: d.nome_original || d.nome || ""
    };
  }

  // ===========================
  // Preenchimento de formulários
  // ===========================
  function preencherFormularioPreverCraf(d) {
    log("Preenchendo modal Pré-visualizar com dados normalizados:", d);

    setSelectMatchById("crafTipo", d.tipo);
    setSelectMatchById("crafFuncionamento", d.funcionamento);
    setSelectMatchById("crafEmissor", d.emissor_craf);
    setSelectMatchById("crafCategoria", d.categoria_adquirente);

    setValById("crafMarca", d.marca);
    setValById("crafModelo", d.modelo);
    setValById("crafCalibre", d.calibre);
    setValById("crafNumeroSerie", d.numero_serie);
    setValById("crafSigma", d.numero_sigma);

    const dt = d.data_validade_craf;
    if (dt && dt.includes("/")) {
      const [dia, mes, ano] = dt.split("/");
      setValById("crafValidade", `${ano}-${mes.padStart(2, "0")}-${dia.padStart(2, "0")}`);
    } else {
      setValById("crafValidade", "");
    }

    const chk = $id("crafValidadeIndet");
    if (chk) chk.checked = !!d.validade_indeterminada;

    setValById("crafCaminho", d.caminho_craf);
  }

  function preencherModalNovaArma(d) {
    const modal = $id("modalNovaArma");
    if (!modal) return;

    const tipoSel = modal.querySelector("select[name='tipo']");
    const funcSel = modal.querySelector("select[name='funcionamento']");
    const emisSel = modal.querySelector("select[name='emissor_craf']");
    const catSel  = modal.querySelector("select[name='categoria_adquirente']");

    if (tipoSel) setSelectMatch(tipoSel, d.tipo);
    if (funcSel) setSelectMatch(funcSel, d.funcionamento);
    if (emisSel) setSelectMatch(emisSel, d.emissor_craf);
    if (catSel)  setSelectMatch(catSel, d.categoria_adquirente);

    setInput(modal, "marca", d.marca);
    setInput(modal, "modelo", d.modelo);
    setInput(modal, "calibre", d.calibre);
    setInput(modal, "numero_serie", d.numero_serie);
    setInput(modal, "numero_sigma", d.numero_sigma);

    if (d.data_validade_craf && d.data_validade_craf.includes("/")) {
      const [dia, mes, ano] = d.data_validade_craf.split("/");
      setInput(modal, "data_validade_craf", `${ano}-${mes.padStart(2, "0")}-${dia.padStart(2, "0")}`);
    } else {
      setInput(modal, "data_validade_craf", "");
    }

    const chk = modal.querySelector("input[name='validade_indeterminada']");
    if (chk) chk.checked = !!d.validade_indeterminada;

    const hidden = modal.querySelector("input[name='caminho_craf']");
    if (hidden) hidden.value = d.caminho_craf || "";
  }

  function preencherModalEditarArma(armaId, d) {
    const modal = $id("modalEditarArma" + armaId);
    if (!modal) return;

    const tipoSel = modal.querySelector("select[name='tipo']");
    const funcSel = modal.querySelector("select[name='funcionamento']");
    const emisSel = modal.querySelector("select[name='emissor_craf']");
    const catSel  = modal.querySelector("select[name='categoria_adquirente']");

    if (tipoSel) setSelectMatch(tipoSel, d.tipo);
    if (funcSel) setSelectMatch(funcSel, d.funcionamento);
    if (emisSel) setSelectMatch(emisSel, d.emissor_craf);
    if (catSel)  setSelectMatch(catSel, d.categoria_adquirente);

    setInput(modal, "marca", d.marca);
    setInput(modal, "modelo", d.modelo);
    setInput(modal, "calibre", d.calibre);
    setInput(modal, "numero_serie", d.numero_serie);
    setInput(modal, "numero_sigma", d.numero_sigma);

    if (d.data_validade_craf && d.data_validade_craf.includes("/")) {
      const [dia, mes, ano] = d.data_validade_craf.split("/");
      setInput(modal, "data_validade_craf", `${ano}-${mes.padStart(2, "0")}-${dia.padStart(2, "0")}`);
    } else {
      setInput(modal, "data_validade_craf", "");
    }

    const chk = modal.querySelector("input[name='validade_indeterminada']");
    if (chk) chk.checked = !!d.validade_indeterminada;

    const hidden = modal.querySelector("input[name='caminho_craf']");
    if (hidden) hidden.value = d.caminho_craf || "";
  }

  function setInput(scope, name, val) {
    const el = scope.querySelector(`input[name='${name}']`);
    if (!el) return;
    const v = val ?? "";
    el.value = v;
    try { el.setAttribute("value", v); } catch (_) {}
  }

  function setSelectMatch(sel, target) {
    const wanted = (target ?? "").toString().trim();
    if (!wanted) { sel.value = ""; return; }

    const byValue = Array.from(sel.options).find(
      (o) => (o.value || "").toLowerCase() === wanted.toLowerCase()
    );
    if (byValue) { sel.value = byValue.value; return; }

    const byLabel = Array.from(sel.options).find(
      (o) => (o.text || "").toLowerCase() === wanted.toLowerCase()
    );
    if (byLabel) { sel.value = byLabel.value; return; }

    sel.value = "";
  }

  // ===========================
  // Modal Pré-visualização CRAF
  // ===========================
  function abrirModalPreverCraf(dados) {
    const modalEl = $id("preverCrafModal");
    if (!modalEl) return;

    modalEl.ocrData = dados;

    if (!modalEl.listenerAttached) {
        modalEl.addEventListener("shown.bs.modal", (ev) => {
            const d = ev.target.ocrData;
            if (d) {
                preencherFormularioPreverCraf(d);
                delete ev.target.ocrData;
            }
        });
        modalEl.listenerAttached = true;
    }

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }

  // ===========================
  // Upload → OCR
  // ===========================
  async function uploadCraf(clienteId, file) {
    const fd = new FormData();
    fd.append("file", file);

    const res = await fetch(`/uploads/${clienteId}/craf`, { method: "POST", body: fd });
    if (!res.ok) throw new Error("Erro no upload do CRAF: " + res.status);

    const json = await res.json();
    log("OCR bruto recebido:", json);
    return normalizeDados(json);
  }

  // ===========================
  // Bindings ao carregar a página
  // ===========================
  document.addEventListener("DOMContentLoaded", () => {
    const uploadForm = $id("formUploadCraf");
    if (uploadForm) {
      uploadForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const file = uploadForm.querySelector("input[type='file']")?.files?.[0];
        if (!file) return alert("Selecione um arquivo.");
        const clienteId = uploadForm.dataset.clienteId;

        try {
          const dados = await uploadCraf(clienteId, file);
          abrirModalPreverCraf(dados);
        } catch (err) {
          console.error(err);
          alert("Erro ao processar CRAF: " + err.message);
        }
      });
    }

    const uploadNovaArma = $id("uploadNovaArma");
    if (uploadNovaArma) {
      uploadNovaArma.addEventListener("change", async function () {
        const clienteId = uploadForm?.dataset?.clienteId;
        const file = this.files?.[0];
        if (!clienteId || !file) return;

        try {
          const dados = await uploadCraf(clienteId, file);
          preencherModalNovaArma(dados);
        } catch (err) {
          console.error(err);
          alert("Erro ao processar CRAF: " + err.message);
        }
      });
    }

    document.querySelectorAll("[id^='uploadEditarArma']").forEach((input) => {
      input.addEventListener("change", async function () {
        const armaId = this.id.replace("uploadEditarArma", "");
        const clienteId = uploadForm?.dataset?.clienteId;
        const file = this.files?.[0];
        if (!clienteId || !armaId || !file) return;

        try {
          const dados = await uploadCraf(clienteId, file);
          preencherModalEditarArma(armaId, dados);
        } catch (err) {
          console.error(err);
          alert("Erro ao processar CRAF: " + err.message);
        }
      });
    });
  });
})();
