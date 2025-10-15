// ======================
// JS - NOTIFICAÇÕES (layout refinado)
// ======================

document.addEventListener("DOMContentLoaded", () => {
  const tabela = document.querySelector("#tabelaNotificacoes tbody");
  const form = document.querySelector("#filtrosForm");
  const btnReload = document.querySelector("#btnReload");

  const capitalize = (str) =>
    str ? str.charAt(0).toUpperCase() + str.slice(1).toLowerCase() : "-";

  async function carregarNotificacoes() {
    tabela.innerHTML = `
      <tr><td colspan="8" class="text-center text-muted py-3">
      <div class="spinner-border text-secondary me-2" role="status"></div> Carregando...
      </td></tr>`;

    const params = new URLSearchParams(new FormData(form)).toString();
    const resp = await fetch(`/notificacoes/api?${params}`);
    const data = await resp.json();

    if (!data.data || data.data.length === 0) {
      tabela.innerHTML = `
        <tr>
          <td colspan="8" class="text-center text-muted py-4">
            <i class="fas fa-bell-slash fa-lg mb-2 d-block"></i>
            <span>Nenhuma notificação disponível no momento</span>
          </td>
        </tr>`;
      return;
    }

tabela.innerHTML = data.data.map(n => {
  // 🔹 Limpa redundância do nome do cliente no final da mensagem
  let msg = n.mensagem || "";
  const nome = n.cliente_nome?.trim();
  if (nome && msg.toLowerCase().endsWith(nome.toLowerCase())) {
    msg = msg.replace(new RegExp(`\\s*[—-]\\s*${nome}$`, "i"), "").trim();
  }

  // 🔹 Função auxiliar para deixar iniciais maiúsculas
  const capitalize = (txt) => txt ? txt.charAt(0).toUpperCase() + txt.slice(1).toLowerCase() : "-";

  return `
    <tr data-id="${n.id}">
      <td>${n.data_envio}</td>
      <td>${n.cliente_nome || "-"}</td>
      <td>${capitalize(n.tipo)}</td>
      <td>${capitalize(n.nivel)}</td>
      <td class="col-mensagem">${msg}</td>
      <td>${capitalize(n.meio)}</td>
      <td>
        <span class="badge ${n.status === "lido" ? "bg-success" : "bg-warning text-dark"}">
          ${capitalize(n.status)}
        </span>
      </td>
      <td>
        ${n.status !== "lido"
          ? `<button class="btn btn-sm btn-outline-success btn-lida">
               <i class="fas fa-check"></i> Marcar como lida
             </button>`
          : `<small class="text-muted">—</small>`}
      </td>
    </tr>
  `;
}).join("");


    document.querySelectorAll(".btn-lida").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const row = e.target.closest("tr");
        const id = row.dataset.id;
        await marcarComoLida(id, row);
      });
    });
  }

  async function marcarComoLida(id, row) {
    const resp = await fetch(`/notificacoes/api/${id}/lida`, { method: "POST" });
    if (resp.ok) {
      row.querySelector("td:nth-child(7)").innerHTML = `<span class="badge bg-success">Lido</span>`;
      row.querySelector("td:nth-child(8)").innerHTML = `<small class="text-muted">—</small>`;
      row.style.opacity = 0.7;
      atualizarBadge();
    }
  }

  async function atualizarBadge() {
    const badge = document.querySelector("#badgeNotificacoes");
    if (badge) {
      const resp = await fetch("/notificacoes/api?status=enviado&per_page=1");
      const data = await resp.json();
      const total = data.total || 0;
      badge.textContent = total;
      badge.classList.toggle("d-none", total === 0);
    }
  }

  form.addEventListener("submit", e => {
    e.preventDefault();
    carregarNotificacoes();
  });

  btnReload?.addEventListener("click", () => carregarNotificacoes());

  carregarNotificacoes();
});
