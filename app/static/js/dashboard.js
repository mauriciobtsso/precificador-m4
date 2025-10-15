// ======================================================
// DASHBOARD M4 – Revisado (v4.1 Estável com Notificações)
// ======================================================

(() => {
  const log = (...a) => console.log("[Dashboard]", ...a);
  const API_CLIENTES = "/clientes/api";
  const API_NOTIFICACOES = "/notificacoes/api?status=enviado&per_page=5";
  const REFRESH_INTERVAL = 60000; // 60s

  // Elementos DOM
  const elResumo = document.querySelector("#dashboard-resumo");
  const elTimeline = document.querySelector("#dashboard-timeline");
  const elNotif = document.querySelector("#dashboard-notificacoes");

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
    isNaN(v) ? "R$ 0,00" : `R$ ${v.toFixed(2).replace(".", ",")}`;

  const formatarData = (isoString) => {
    if (!isoString) return "";
    const d = new Date(isoString);
    return d.toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
    });
  };

  // ===============================
  // Funções de Fetch
  // ===============================
  async function fetchJSON(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    return await resp.json();
  }

  const fetchResumo = () => fetchJSON(`${API_CLIENTES}/resumo`);
  const fetchTimeline = () => fetchJSON(`${API_CLIENTES}/timeline`);
  const fetchNotificacoes = () => fetchJSON(API_NOTIFICACOES);

  // ===============================
  // Renderização: Resumo
  // ===============================
  function renderResumo(data) {
    if (!elResumo) return;
    const html = `
      <div class="row g-3">
        ${cardResumo("fa-users", "Clientes", data.clientes_total, "primary")}
        ${cardResumo("fa-id-card", "Documentos Válidos", data.documentos_validos, "success")}
        ${cardResumo("fa-exclamation-triangle", "Doc. Vencidos", data.documentos_vencidos, "danger")}
        ${cardResumo("fa-boxes", "Produtos", data.produtos_total, "dark")}
        ${cardResumo("fa-tasks", "Processos Ativos", data.processos_ativos, "warning")}
        ${cardResumo("fa-dollar-sign", "Vendas no mês", formatarValor(data.vendas_mes), "info")}
      </div>`;
    elResumo.innerHTML = html;
  }

  const cardResumo = (icone, titulo, valor, cor) => `
    <div class="col-6 col-md-4 col-lg-2">
      <div class="card shadow-sm text-center h-100 border-0">
        <div class="card-body py-3">
          <i class="fas ${icone} fa-2x text-${cor} mb-2"></i>
          <h6 class="text-muted mb-1">${titulo}</h6>
          <h5 class="fw-bold text-${cor}">${valor ?? 0}</h5>
        </div>
      </div>
    </div>`;

  // ===============================
  // Renderização: Notificações Pendentes
  // ===============================
  function renderNotificacoes(data) {
    if (!elNotif) return;

    const pendentes = data.data?.filter((n) => n.status === "enviado") || [];

    if (!pendentes.length) {
      elNotif.innerHTML = `
        <div class="alert alert-success mb-0 text-center">
          Nenhuma notificação pendente 🎯
        </div>`;
      return;
    }

    const html = `
      <div class="d-flex justify-content-between align-items-center mb-2">
        <div>
          <i class="fas fa-bell text-danger me-2"></i>
          <strong>Notificações Pendentes</strong>
        </div>
        <a href="/notificacoes" class="btn btn-outline-danger btn-sm">
          <i class="fas fa-eye me-1"></i> Ver todas
        </a>
      </div>
      <ul class="list-group small shadow-sm">
        ${pendentes
          .map(
            (n) => `
          <li class="list-group-item d-flex justify-content-between align-items-center">
            <div>
              <i class="fas fa-circle text-warning me-2"></i>
              ${n.mensagem}
            </div>
            <span class="badge bg-light text-dark">${n.cliente_nome || "-"}</span>
          </li>`
          )
          .join("")}
      </ul>`;
    elNotif.innerHTML = html;
  }

  // ===============================
  // Renderização: Timeline
  // ===============================
  function renderTimeline(dados) {
    if (!elTimeline) return;
    const eventos = dados.eventos || [];
    if (!eventos.length) {
      elTimeline.innerHTML = `<div class="alert alert-light text-center mb-0">Sem eventos recentes</div>`;
      return;
    }

    const icones = {
      documento: "fa-file-alt text-primary",
      processo: "fa-tasks text-warning",
      venda: "fa-shopping-cart text-success",
      comunicacao: "fa-envelope text-info",
    };

    const html = `
      <ul class="list-group list-group-flush small">
        ${eventos
          .map(
            (e) => `
          <li class="list-group-item">
            <i class="fas ${icones[e.tipo] || "fa-info-circle text-muted"} me-2"></i>
            <strong>${e.tipo.toUpperCase()}</strong> — ${e.descricao}
            <span class="float-end text-muted">${formatarData(e.data)}</span>
          </li>`
          )
          .join("")}
      </ul>`;
    elTimeline.innerHTML = html;
  }

  // ===============================
  // Carregamento inicial
  // ===============================
  async function carregarDashboard() {
    log("Carregando Dashboard...");
    if (elResumo) elResumo.innerHTML = spinnerHTML("Carregando resumo...");
    if (elNotif) elNotif.innerHTML = spinnerHTML("Verificando notificações...");
    if (elTimeline) elTimeline.innerHTML = spinnerHTML("Carregando eventos...");

    try {
      const [resumo, notificacoes, timeline] = await Promise.all([
        fetchResumo(),
        fetchNotificacoes(),
        fetchTimeline(),
      ]);

      renderResumo(resumo);
      renderNotificacoes(notificacoes);
      renderTimeline(timeline);
      log("✅ Dashboard atualizado.");
    } catch (err) {
      if (elResumo) elResumo.innerHTML = erroHTML("Falha ao carregar resumo.");
      if (elNotif) elNotif.innerHTML = erroHTML("Erro ao buscar notificações.");
      if (elTimeline) elTimeline.innerHTML = erroHTML("Erro ao buscar timeline.");
      console.error(err);
    }
  }

  // ===============================
  // Inicialização automática
  // ===============================
  document.addEventListener("DOMContentLoaded", () => {
    carregarDashboard();
    setInterval(carregarDashboard, REFRESH_INTERVAL);
  });
})();
