// ===========================================================
// MÓDULO: COMPRAS_IMPORTAR.JS — Sprint 7B Final
// ===========================================================
(() => {
  console.log("[M4] compras_importar.js carregado ✅");

  const form = document.getElementById("formImportar");
  const resultadoDiv = document.getElementById("resultado");
  const wrapTabela = document.getElementById("wrapTabela");
  const tbody = document.getElementById("tbodyItens");
  const resumo = document.getElementById("resumoImport");
  const btnSalvar = document.getElementById("btnSalvarNF");

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const file = document.getElementById("xml").files[0];
    if (!file) return alert("Selecione um arquivo XML.");

    const formData = new FormData();
    formData.append("xml", file);

    resultadoDiv.innerHTML = `<div class="alert alert-info">Processando NF... aguarde.</div>`;
    wrapTabela.classList.add("d-none");
    tbody.innerHTML = "";
    btnSalvar.classList.add("d-none");

    try {
      const res = await fetch("/compras/importar", { method: "POST", body: formData });
      const data = await res.json();

      if (!data.success) {
        resultadoDiv.innerHTML = `<div class="alert alert-danger">❌ ${data.message || "Erro ao processar NF"}</div>`;
        return;
      }

      resultadoDiv.innerHTML = `
        <div class="alert alert-success">
          NF importada com sucesso! Confira os itens abaixo.<br>
          <b>Fornecedor:</b> ${data.fornecedor || "-"}<br>
          <b>Chave:</b> ${data.chave || "-"}<br>
          <b>Total:</b> R$ ${Number(data.valor_total || 0).toFixed(2)}
        </div>
      `;

      if (Array.isArray(data.itens)) {
        data.itens.forEach((item, i) => {
          tbody.insertAdjacentHTML("beforeend", `
            <tr>
              <td>${i + 1}</td>
              <td>${item.descricao || "-"}</td>
              <td>${item.marca || "-"}</td>
              <td>${item.modelo || "-"}</td>
              <td>${item.calibre || "-"}</td>
              <td>${item.lote || item.numero_serie || "-"}</td>
              <td class="text-end">${item.quantidade || 0}</td>
              <td class="text-end">${item.valor_unitario?.toFixed(2) || "0.00"}</td>
              <td class="text-end">${item.valor_total?.toFixed(2) || "0.00"}</td>
            </tr>
          `);
        });
      }

      resumo.textContent = `${data.itens.length} itens encontrados.`;
      wrapTabela.classList.remove("d-none");
      btnSalvar.classList.remove("d-none");

      btnSalvar.onclick = async () => {
        btnSalvar.disabled = true;
        const salvarRes = await fetch("/compras/salvar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });
        const salvarData = await salvarRes.json();
        if (salvarData.success) {
          alert("✅ NF salva com sucesso!");
          location.reload();
        } else {
          alert("Erro ao salvar NF: " + salvarData.message);
        }
        btnSalvar.disabled = false;
      };
    } catch (err) {
      console.error("Erro:", err);
      resultadoDiv.innerHTML = `<div class="alert alert-danger">Erro inesperado ao importar NF.</div>`;
    }
  });
})();
