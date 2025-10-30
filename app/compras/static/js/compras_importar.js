// ============================================================
// MÓDULO: COMPRAS_IMPORTAR.JS — v7B+
// Exibe cabeçalho + itens + botão de salvamento AJAX
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
  console.log("[Compras] compras_importar.js carregado");

  const form = document.getElementById("formImportar");
  const resultado = document.getElementById("resultado");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const fd = new FormData(form);
    resultado.innerHTML = `
      <div class="alert alert-info mt-3">
        <i class="fas fa-spinner fa-spin me-2"></i> Processando XML...
      </div>`;

    try {
      const resp = await fetch("/compras/importar", { method: "POST", body: fd });
      const data = await resp.json();

      if (!data.success) {
        resultado.innerHTML = `
          <div class="alert alert-danger mt-3">
            <i class="fas fa-times-circle me-2"></i>
            ${data.message || "Erro ao processar o XML."}
          </div>`;
        return;
      }

      renderNF(data);
    } catch (err) {
      console.error("Erro no upload:", err);
      resultado.innerHTML = `
        <div class="alert alert-danger mt-3">
          <i class="fas fa-times-circle me-2"></i> Erro no upload: ${err}
        </div>`;
    }
  });

  // ============================================================
  // Função de renderização principal
  // ============================================================
  function renderNF(data) {
    const fornecedor = data.fornecedor || "Fornecedor não informado";
    const valorTotal = data.valor_total || data.valor_total_nf || 0;
    const chave = data.chave || "";
    const numero = data.numero || "";
    const dataEmissao = data.data_emissao || "";
    const itens = data.itens || [];

    // Cabeçalho
    let html = `
      <div class="card shadow-sm border-0 mb-4">
        <div class="card-body">
          <h5 class="card-title mb-3">
            <i class="fas fa-file-invoice me-2 text-orange"></i>
            NF importada com sucesso! Confira os dados abaixo:
          </h5>
          <p><strong>Fornecedor:</strong> ${fornecedor}</p>
          <p><strong>Valor Total:</strong> R$ ${parseFloat(valorTotal).toFixed(2)}</p>
          <p><strong>Chave NF-e:</strong> ${chave}</p>
          <p><strong>Número:</strong> ${numero}</p>
          <p><strong>Data de Emissão:</strong> ${dataEmissao}</p>
        </div>
      </div>
    `;

    // Tabela de Itens
    if (itens.length === 0) {
      html += `
        <div class="alert alert-warning">
          <i class="fas fa-exclamation-triangle me-2"></i>
          Nenhum item encontrado na NF.
        </div>`;
      resultado.innerHTML = html;
      return;
    }

    html += `
      <div class="table-responsive mt-3">
        <table class="table table-striped align-middle">
          <thead class="table-light">
            <tr>
              <th>#</th>
              <th>Descrição</th>
              <th>Qtd</th>
              <th>Vlr Unit.</th>
              <th>Marca</th>
              <th>Modelo</th>
              <th>Calibre</th>
              <th>Lote</th>
              <th>Nº Série</th>
            </tr>
          </thead>
          <tbody>
    `;

    itens.forEach((it, idx) => {
      html += `
        <tr>
          <td>${idx + 1}</td>
          <td>${it.descricao || "-"}</td>
          <td>${it.quantidade}</td>
          <td>R$ ${parseFloat(it.valor_unitario).toFixed(2)}</td>
          <td>${it.marca || "-"}</td>
          <td>${it.modelo || "-"}</td>
          <td>${it.calibre || "-"}</td>
          <td>${it.lote || "-"}</td>
          <td>${it.numero_serie || "-"}</td>
        </tr>
      `;
    });

    html += `
          </tbody>
        </table>
      </div>

      <div class="text-end mt-4">
        <button id="btnSalvarNF" class="btn btn-success">
          <i class="fas fa-save me-2"></i> Salvar NF no Sistema
        </button>
      </div>
    `;

    resultado.innerHTML = html;

    // Vincular o botão de salvamento
    document.getElementById("btnSalvarNF").addEventListener("click", () => salvarNF(data));
  }

  // ============================================================
  // Função AJAX para salvar NF no banco
  // ============================================================
  async function salvarNF(data) {
    const btn = document.getElementById("btnSalvarNF");
    btn.disabled = true;
    btn.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i> Salvando...`;

    try {
      const resp = await fetch("/compras/salvar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const result = await resp.json();

      if (result.success) {
        resultado.innerHTML = `
          <div class="alert alert-success mt-4">
            <i class="fas fa-check-circle me-2"></i>
            NF salva com sucesso! (ID: ${result.nf_id})
          </div>`;
      } else {
        resultado.innerHTML = `
          <div class="alert alert-warning mt-4">
            <i class="fas fa-exclamation-triangle me-2"></i>
            ${result.message || "Não foi possível salvar a NF."}
          </div>`;
      }
    } catch (err) {
      console.error("Erro ao salvar NF:", err);
      resultado.innerHTML = `
        <div class="alert alert-danger mt-4">
          <i class="fas fa-times-circle me-2"></i> Erro ao salvar NF: ${err}
        </div>`;
    }
  }
});
