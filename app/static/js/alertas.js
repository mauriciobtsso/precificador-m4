// ======================
// ALERTAS - FRONTEND (v3 Dinâmico e Otimizado)
// ======================

(() => {
  const log = (...a) => console.log("[ALERTAS]", ...a);

  const API_URL = "/api/alertas";
  const tabela = document.querySelector("#tabela-alertas tbody");
  const formFiltros = document.querySelector("#form-filtros");
  const paginacaoEl = document.querySelector(".pagination");
  const infoEl = document.querySelector(".card-footer .text-muted");

  let paginaAtual = 1;
  let totalPaginas = 1;
  let debounceTimer = null;

  // ======================
  // UTIL: Leitura dos filtros
  // ======================
  function getFiltros() {
    const formData = new FormData(formFiltros);
    const params = {};
    for (const [k, v] of formData.entries()) {
      if (v && v.trim() !== "") params[k] = v.trim();
    }
    params.page = paginaAtual;
    return params;
  }

  // ======================
  // UTIL: Monta URL com querystring
  // ======================
  function montarUrl(base, params) {
    const query = new URLSearchParams(params).toString();
    return `${base}?${query}`;
  }

  // ======================
  // UTIL: Cria linha da tabela
  // ======================
  function criarLinha(alerta, idx) {
    const tipoIcone = {
      documento: "📄 Documento",
      arma: "🔫 Arma",
      processo: "📁 Processo",
      cr: "🪪 CR"
    };

    const nivelCor = {
      alto: "🔴 Alto",
      médio: "🟡 Médio",
      medio: "🟡 Médio",
      baixo: "🟢 Baixo"
    };

    return `
      <tr>
        <td>${idx + 1}</td>
        <td><span class="tipo tipo-${alerta.tipo}">${tipoIcone[alerta.tipo] || alerta.tipo}</span></td>
        <td><span class="nivel nivel-${alerta.nivel}">${nivelCor[alerta.nivel] || alerta.nivel}</span></td>
        <td>${alerta.cliente || "-"}</td>
        <td>${alerta.mensagem || "-"}</td>
        <td>${alerta.data || "-"}</td>
        <td>
          <a href="/clientes/${alerta.cliente_id}" class="btn btn-sm btn-outline-primary">
            Ver cliente
          </a>
        </td>
      </tr>
    `;
  }

  // ======================
  // UTIL: Mostra estado de carregamento
  // ======================
  function mostrarCarregando() {
    tabela.innerHTML = `
      <tr>
        <td colspan="7" class="text-center text-muted py-3">
          <div class="spinner-border spinner-border-sm text-primary me-2"></div>
          Carregando alertas...
        </td>
      </tr>
    `;
  }

  // ======================
  // UTIL: Renderiza tabela
  // ======================
  function renderizarTabela(dados) {
    if (!dados || !dados.data || dados.data.length === 0) {
      tabela.innerHTML = `
        <tr>
          <td colspan="7" class="text-center text-muted py-3">
            Nenhum alerta encontrado com os filtros aplicados.
          </td>
        </tr>
      `;
      infoEl.textContent = "Nenhum alerta encontrado";
      return;
    }

    tabela.innerHTML = dados.data
      .map((a, i) => criarLinha(a, i + (dados.page - 1) * 20))
      .join("");

    infoEl.textContent = `Exibindo página ${dados.page} de ${dados.pages} (${dados.total} alertas)`;
    totalPaginas = dados.pages;
    renderizarPaginacao();
  }

  // ======================
  // UTIL: Renderiza paginação
  // ======================
  function renderizarPaginacao() {
    if (!paginacaoEl) return;

    let html = "";
    const desativarAnterior = paginaAtual <= 1 ? "disabled" : "";
    const desativarProxima = paginaAtual >= totalPaginas ? "disabled" : "";

    html += `<li class="page-item ${desativarAnterior}">
               <a class="page-link" href="#" data-page="${paginaAtual - 1}">«</a>
             </li>`;

    // Mostra até 5 páginas
    const inicio = Math.max(1, paginaAtual - 2);
    const fim = Math.min(totalPaginas, paginaAtual + 2);

    for (let i = inicio; i <= fim; i++) {
      html += `<li class="page-item ${i === paginaAtual ? "active" : ""}">
                 <a class="page-link" href="#" data-page="${i}">${i}</a>
               </li>`;
    }

    html += `<li class="page-item ${desativarProxima}">
               <a class="page-link" href="#" data-page="${paginaAtual + 1}">»</a>
             </li>`;

    paginacaoEl.innerHTML = html;
  }

  // ======================
  // EVENTO: Clique na paginação
  // ======================
  if (paginacaoEl) {
    paginacaoEl.addEventListener("click", (e) => {
      const link = e.target.closest("a[data-page]");
      if (!link) return;
      e.preventDefault();
      const novaPag = parseInt(link.dataset.page);
      if (novaPag < 1 || novaPag > totalPaginas) return;
      paginaAtual = novaPag;
      carregarAlertas();
    });
  }

  // ======================
  // EVENTO: Mudança de filtros
  // ======================
  if (formFiltros) {
    formFiltros.addEventListener("change", () => {
      paginaAtual = 1;
      carregarAlertas();
    });

    // Busca com debounce (tecla solta)
    const campoBusca = formFiltros.querySelector("input[name='q']");
    if (campoBusca) {
      campoBusca.addEventListener("keyup", () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          paginaAtual = 1;
          carregarAlertas();
        }, 600);
      });
    }
  }

  // ======================
  // CORE: Carregar alertas
  // ======================
  async function carregarAlertas() {
    const params = getFiltros();
    const url = montarUrl(API_URL, params);
    log("Carregando:", url);

    try {
      mostrarCarregando();

      const resp = await fetch(url);
      if (!resp.ok) throw new Error("Erro ao buscar alertas");

      const dados = await resp.json();
      renderizarTabela(dados);
    } catch (err) {
      console.error(err);
      tabela.innerHTML = `
        <tr>
          <td colspan="7" class="text-center text-danger py-3">
            Erro ao carregar alertas. Tente novamente.
          </td>
        </tr>
      `;
      infoEl.textContent = "Erro de carregamento";
    }
  }

  // ======================
  // INICIALIZAÇÃO
  // ======================
  document.addEventListener("DOMContentLoaded", () => {
    carregarAlertas();
  });
})();
  // ======================
  // TOOLTIP & UX Refinements
  // ======================
  document.addEventListener("mouseover", (e) => {
    const el = e.target.closest(".tipo, .nivel");
    if (!el) return;

    const tipo = el.classList.contains("tipo") ? el.textContent.trim() : null;
    const nivel = el.classList.contains("nivel") ? el.textContent.trim() : null;

    const tooltip = document.createElement("div");
    tooltip.className = "tooltip-alerta";
    tooltip.textContent = tipo || nivel;
    document.body.appendChild(tooltip);

    const rect = el.getBoundingClientRect();
    tooltip.style.left = rect.left + window.scrollX + "px";
    tooltip.style.top = rect.top + window.scrollY - 28 + "px";

    el.addEventListener("mouseleave", () => tooltip.remove(), { once: true });
  });
/* ======================
   NOTIFICAÇÕES - Estilo visual
====================== */
.notificacao-item.lida {
  opacity: 0.6;
  background-color: #f8f9fa;
  transition: all 0.3s ease;
}
.notificacao-item .status {
  font-size: 0.9em;
  color: #777;
}


