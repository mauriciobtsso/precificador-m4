// ======================================================
// DASHBOARD M4 – v5 (KPIs + Gráficos + Integração Real)
// ======================================================

(() => {
  const log = (...a) => console.log("[M4-Dashboard]", ...a);
  const REFRESH_INTERVAL = 60000; // 60s

  // ===============================
  // Elementos principais
  // ===============================
  const elResumo = document.querySelector("#dashboard-resumo");
  const elTimeline = document.querySelector("#dashboard-timeline");
  const chartDocsCtx = document.getElementById("chartDocs");
  const chartArmasCtx = document.getElementById("chartArmas");

  let chartDocs, chartArmas;

  // ===============================
  // Helpers
  // ===============================
  const spinnerHTML = (msg = "Carregando...") => `
    <div class="d-flex align-items-center justify-content-center py-4 text-muted">
      <div class="spinner-border text-secondary me-2" role="status"></div>
      <span>${msg}</span>
    </div>`;

  const erroHTML = (msg = "Erro ao carregar dados.") =>
    `<div class="alert alert-danger shadow-sm">${msg}</div>`;

  const formatarValor = (v) =>
    isNaN(v) ? "R$ 0,00" : `R$ ${parseFloat(v).toFixed(2).replace(".", ",")}`;

  const formatarData = (isoString) => {
    if (!isoString) return "";
    const d = new Date(isoString);
    return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  };

  async function fetchJSON(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    return await resp.json();
  }

  // ===============================
  // RENDERIZAÇÃO DOS CARDS DE RESUMO
  // ===============================
  function renderResumo(data) {
    if (!elResumo) return;
    const html = `
      <div class="row g-3">
        ${cardResumo("fa-boxes-stacked", "Produtos", data.produtos_total, "dark")}
        ${cardResumo("fa-users", "Clientes", data.clientes_total, "primary")}
        ${cardResumo("fa-file-shield", "Documentos válidos", data.documentos_validos, "success")}
        ${cardResumo("fa-triangle-exclamation", "Vencidos", data.documentos_vencidos, "danger")}
        ${cardResumo("fa-hand-holding-usd", "Vendas do mês", formatarValor(data.vendas_mes), "info")}
        ${cardResumo("fa-chart-line", "Ticket médio", formatarValor(data.ticket_medio), "warning")}
      </div>`;
    elResumo.innerHTML = html;
  }

  const cardResumo = (icone, titulo, valor, cor) => `
    <div class="col-6 col-md-4 col-lg-2">
      <div class="card text-center shadow-sm border-0 h-100">
        <div class="card-body py-3">
          <i class="fas ${icone} fa-2x text-${cor} mb-2"></i>
          <h6 class="text-muted mb-1">${titulo}</h6>
          <h5 class="fw-bold text-${cor}">${valor ?? 0}</h5>
        </div>
      </div>
    </div>`;

  // ===============================
  // RENDERIZAÇÃO DA TIMELINE
  // ===============================
  function renderTimeline(data) {
    if (!elTimeline) return;
    const eventos = data.eventos || [];
    if (!eventos.length) {
      elTimeline.innerHTML = `<div class="alert alert-light text-center mb-0">Sem eventos recentes</div>`;
      return;
    }

    const icones = {
      documento: "fa-file-alt text-primary",
      processo: "fa-tasks text-warning",
      venda: "fa-cart-shopping text-success",
      cliente: "fa-user text-info",
    };

    elTimeline.innerHTML = `
      <ul class="timeline">
        ${eventos
          .map(
            (e) => `
          <li>
            <small>${formatarData(e.data)}</small>
            <strong><i class="fas ${icones[e.tipo] || "fa-info-circle text-muted"} me-2"></i>${e.tipo.toUpperCase()}</strong>
            — ${e.descricao}
          </li>`
          )
          .join("")}
      </ul>`;
  }

  // ===============================
  // GRÁFICOS (Chart.js)
  // ===============================
  function renderGraficos(data) {
    // --- Documentos por status ---
    if (chartDocs) chartDocs.destroy();
    chartDocs = new Chart(chartDocsCtx, {
      type: "doughnut",
      data: {
        labels: ["Válidos", "Vencidos"],
        datasets: [
          {
            data: [data.documentos_validos || 0, data.documentos_vencidos || 0],
            backgroundColor: ["#198754", "#dc3545"],
            borderWidth: 1,
          },
        ],
      },
      options: {
        plugins: { legend: { position: "bottom" } },
      },
    });

    // --- Produtos por categoria ---
    if (chartArmas) chartArmas.destroy();
    const categorias = data.categorias?.map((c) => c.nome) || [];
    const totais = data.categorias?.map((c) => c.total) || [];
    chartArmas = new Chart(chartArmasCtx, {
      type: "bar",
      data: {
        labels: categorias,
        datasets: [
          {
            label: "Qtd. Produtos",
            data: totais,
            backgroundColor: "#0d6efd88",
            borderColor: "#0d6efd",
            borderWidth: 1,
          },
        ],
      },
      options: {
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 } },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  // ===============================
  // CARREGAMENTO PRINCIPAL
  // ===============================
  async function carregarDashboard() {
    try {
      elResumo.innerHTML = spinnerHTML("Carregando resumo...");
      elTimeline.innerHTML = spinnerHTML("Carregando atividades...");
      log("🔄 Atualizando Dashboard...");

      const [resumo, timeline] = await Promise.all([
        fetchJSON("/dashboard/api/resumo"),
        fetchJSON("/dashboard/api/timeline"),
      ]);

      renderResumo(resumo);
      renderTimeline(timeline);
      renderGraficos(resumo);

      log("✅ Dashboard atualizado.");
    } catch (err) {
      console.error("❌ Erro no dashboard:", err);
      elResumo.innerHTML = erroHTML("Falha ao carregar resumo.");
      elTimeline.innerHTML = erroHTML("Falha ao carregar atividades.");
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    carregarDashboard();
    setInterval(carregarDashboard, REFRESH_INTERVAL);
  });
})();
