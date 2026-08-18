// ======================================================
// DASHBOARD M4 – v7 (ES5 COMPATIBLE - NO FETCH/PROMISE)
// ======================================================

(function() {
    var log = function(msg) { console.log("[M4-Dashboard]", msg); };
    var REFRESH_INTERVAL = 300000; // 5 min

    var elResumo = document.querySelector("#dashboard-resumo");
    var elTimeline = document.querySelector("#dashboard-timeline");
    var chartDocsCtx = document.getElementById("chartDocs");
    var chartArmasCtx = document.getElementById("chartArmas");

    var chartDocs, chartArmas;

    var formatarValor = function(v) {
        return "R$ " + (v || 0).toFixed(2).replace('.', ',').replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1.');
    };

    var formatarData = function(isoString) {
        if (!isoString) return "";
        var d = new Date(isoString);
        var dia = ("0" + d.getDate()).slice(-2);
        var mes = ("0" + (d.getMonth() + 1)).slice(-2);
        var hora = ("0" + d.getHours()).slice(-2);
        var min = ("0" + d.getMinutes()).slice(-2);
        return dia + "/" + mes + " " + hora + ":" + min;
    };

    var getJSON = function(url, callback) {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', url, true);
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                if (xhr.status === 200) {
                    callback(null, JSON.parse(xhr.responseText));
                } else {
                    callback(new Error(xhr.statusText));
                }
            }
        };
        xhr.send();
    };

    var renderResumo = function(data) {
        if (!elResumo) return;
        
        var cards = [
            { icon: "fa-boxes-stacked", label: "Produtos", val: data.produtos_total, color: "dark" },
            { icon: "fa-users", label: "Clientes", val: data.clientes_total, color: "primary" },
            { icon: "fa-gun", label: "Armas", val: data.total_armas, color: "danger" },
            { icon: "fa-file-shield", label: "Docs Válidos", val: data.documentos_validos, color: "success" },
            { icon: "fa-hand-holding-usd", label: "Vendas (Mês)", val: formatarValor(data.vendas_mes), color: "info" },
            { icon: "fa-chart-line", label: "Ticket Médio", val: formatarValor(data.ticket_medio), color: "warning" }
        ];

        var html = "";
        for (var i = 0; i < cards.length; i++) {
            var c = cards[i];
            html += '<div class="col-6 col-md-4 col-lg-2">' +
                    '    <div class="card kpi-card-v2 shadow-sm border-0 h-100">' +
                    '        <div class="card-body p-3">' +
                    '            <div class="kpi-icon-v2 bg-' + c.color + ' bg-opacity-10 text-' + c.color + '">' +
                    '                <i class="fas ' + c.icon + '"></i>' +
                    '            </div>' +
                    '            <h6 class="text-muted small mb-1">' + c.label + '</h6>' +
                    '            <h5 class="fw-bold mb-0 text-dark">' + c.val + '</h5>' +
                    '        </div>' +
                    '    </div>' +
                    '</div>';
        }
        elResumo.innerHTML = html;
    };

    var renderTimeline = function(data) {
        if (!elTimeline) return;
        var eventos = data.eventos || [];
        
        if (!eventos.length) {
            elTimeline.innerHTML = '<div class="text-center py-4 text-muted">Sem atividades recentes</div>';
            return;
        }

        var icones = {
            venda: "fa-shopping-cart text-success",
            produto: "fa-tag text-warning",
            cliente: "fa-user-plus text-info",
            documento: "fa-file-alt text-primary"
        };

        var html = "";
        for (var i = 0; i < eventos.length; i++) {
            var e = eventos[i];
            html += '<div class="timeline-item">' +
                    '    <div class="d-flex justify-content-between align-items-start">' +
                    '        <div>' +
                    '            <span class="d-block fw-bold small"><i class="fas ' + (icones[e.tipo] || 'fa-circle') + ' me-2"></i>' + e.tipo.toUpperCase() + '</span>' +
                    '            <p class="mb-0 text-muted small">' + e.descricao + '</p>' +
                    '        </div>' +
                    '        <span class="badge bg-light text-dark fw-normal" style="font-size: 0.65rem;">' + formatarData(e.data) + '</span>' +
                    '    </div>' +
                    '</div>';
        }
        elTimeline.innerHTML = html;
    };

    var renderGraficos = function(data) {
        if (typeof Chart === 'undefined') return;

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

        if (chartArmas) chartArmas.destroy();
        if (chartArmasCtx) {
            var labels = [];
            var values = [];
            for (var i = 0; i < data.categorias.length; i++) {
                labels.push(data.categorias[i].nome);
                values.push(data.categorias[i].total);
            }
            
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
    };

    var initDashboard = function() {
        log("🔄 Sincronizando dados...");
        getJSON("/dashboard/api/resumo", function(err, resumo) {
            if (err) {
                console.error(err);
                return;
            }
            renderResumo(resumo);
            renderGraficos(resumo);
            
            getJSON("/dashboard/api/timeline", function(err, timeline) {
                if (err) return;
                renderTimeline(timeline);
                log("✅ Dashboard sincronizado.");
            });
        });
    };

    document.addEventListener("DOMContentLoaded", function() {
        initDashboard();
        
        var btnRefresh = document.getElementById("btnRefreshTimeline");
        if (btnRefresh) {
            btnRefresh.onclick = function(e) {
                e.preventDefault();
                initDashboard();
            };
        }
    });
})();
