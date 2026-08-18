// ======================================================
// DASHBOARD M4 – v6 (Performance & UX Refatorada)
// ======================================================

(() => {
    const log = (...a) => console.log("[M4-Dashboard]", ...a);
    const REFRESH_INTERVAL = 300000; // 5 minutos (evita sobrecarga)

    const elResumo = document.querySelector("#dashboard-resumo");
    const elTimeline = document.querySelector("#dashboard-timeline");
    const chartDocsCtx = document.getElementById("chartDocs");
    const chartArmasCtx = document.getElementById("chartArmas");

    let chartDocs, chartArmas;

    const formatarValor = (v) => 
        new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0);

    const formatarData = (isoString) => {
        if (!isoString) return "";
        const d = new Date(isoString);
        return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
    };

    async function fetchJSON(url) {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
        return await resp.json();
    }

    function renderResumo(data) {
        if (!elResumo) return;
        
        const cards = [
            { icon: "fa-boxes-stacked", label: "Produtos", val: data.produtos_total, color: "dark" },
            { icon: "fa-users", label: "Clientes", val: data.clientes_total, color: "primary" },
            { icon: "fa-gun", label: "Armas", val: data.total_armas, color: "danger" },
            { icon: "fa-file-shield", label: "Docs Válidos", val: data.documentos_validos, color: "success" },
            { icon: "fa-hand-holding-usd", label: "Vendas (Mês)", val: formatarValor(data.vendas_mes), color: "info" },
            { icon: "fa-chart-line", label: "Ticket Médio", val: formatarValor(data.ticket_medio), color: "warning" }
        ];

        elResumo.innerHTML = cards.map(c => `
            <div class="col-6 col-md-4 col-lg-2">
                <div class="card kpi-card shadow-sm border-0 h-100">
                    <div class="card-body p-3">
                        <div class="kpi-icon bg-${c.color} bg-opacity-10 text-${c.color}">
                            <i class="fas ${c.icon}"></i>
                        </div>
                        <h6 class="text-muted small mb-1">${c.label}</h6>
                        <h5 class="fw-bold mb-0 text-dark">${c.val}</h5>
                    </div>
                </div>
            </div>
        `).join("");
    }

    function renderTimeline(data) {
        if (!elTimeline) return;
        const eventos = data.eventos || [];
        
        if (!eventos.length) {
            elTimeline.innerHTML = `<div class="text-center py-4 text-muted">Sem atividades recentes</div>`;
            return;
        }

        const icones = {
            venda: "fa-shopping-cart text-success",
            produto: "fa-tag text-warning",
            cliente: "fa-user-plus text-info",
            documento: "fa-file-alt text-primary"
        };

        elTimeline.innerHTML = eventos.map(e => `
            <div class="timeline-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <span class="d-block fw-bold small"><i class="fas ${icones[e.tipo] || 'fa-circle'} me-2"></i>${e.tipo.toUpperCase()}</span>
                        <p class="mb-0 text-muted small">${e.descricao}</p>
                    </div>
                    <span class="badge bg-light text-dark fw-normal" style="font-size: 0.65rem;">${formatarData(e.data)}</span>
                </div>
            </div>
        `).join("");
    }

    function renderGraficos(data) {
        // Gráfico de Documentos (Doughnut)
        if (chartDocs) chartDocs.destroy();
        if (chartDocsCtx) {
            chartDocs = new Chart(chartDocsCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Válidos', 'Vencidos'],
                    datasets: [{
                        data: [data.documentos_validos, data.documentos_vencidos],
                        backgroundColor: ['#22c55e', '#ef4444'],
                        hoverOffset: 4
                    }]
                },
                options: {
                    cutout: '70%',
                    plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } }
                }
            });
        }

        // Gráfico de Categorias (Bar)
        if (chartArmas) chartArmas.destroy();
        if (chartArmasCtx) {
            const labels = data.categorias.map(c => c.nome);
            const values = data.categorias.map(c => c.total);
            
            chartArmas = new Chart(chartArmasCtx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Qtd',
                        data: values,
                        backgroundColor: '#c5a059',
                        borderRadius: 6
                    }]
                },
                options: {
                    indexAxis: 'y',
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { display: false }, ticks: { precision: 0 } },
                        y: { grid: { display: false } }
                    }
                }
            });
        }
    }

    async function initDashboard() {
        try {
            log("🔄 Carregando dados operacionais...");
            const [resumo, timeline] = await Promise.all([
                fetchJSON("/dashboard/api/resumo"),
                fetchJSON("/dashboard/api/timeline")
            ]);

            renderResumo(resumo);
            renderTimeline(timeline);
            renderGraficos(resumo);
            log("✅ Dashboard pronto.");
        } catch (err) {
            console.error("❌ Falha crítica no dashboard:", err);
            if (elResumo) elResumo.innerHTML = `<div class="col-12"><div class="alert alert-danger">Erro ao sincronizar dados. Verifique a conexão.</div></div>`;
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        initDashboard();
        
        const btnRefresh = document.getElementById("btnAtualizarTimeline");
        if (btnRefresh) {
            btnRefresh.addEventListener("click", (e) => {
                e.preventDefault();
                initDashboard();
            });
        }
    });
})();
