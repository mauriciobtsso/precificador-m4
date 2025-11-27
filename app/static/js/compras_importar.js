// ============================================================
// MÓDULO: Importação de XML (Compras)
// ============================================================

window.dadosNF = null; // Armazena o JSON do XML parsed

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("formImportar");
  const btnImportar = document.getElementById("btnImportar");
  const resultadoDiv = document.getElementById("resultado");
  const wrapTabela = document.getElementById("wrapTabela");
  const tbody = document.getElementById("tbodyItens");
  const btnSalvar = document.getElementById("btnSalvarNF");
  const resumoImport = document.getElementById("resumoImport");

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      
      // Limpa estado anterior
      resultadoDiv.innerHTML = "";
      wrapTabela.classList.add("d-none");
      tbody.innerHTML = "";
      btnImportar.disabled = true;
      btnImportar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processando...';

      const formData = new FormData(form);

      try {
        const resp = await fetch("/compras/importar", {
          method: "POST",
          body: formData,
        });
        
        const data = await resp.json();

        if (data.success) {
          window.dadosNF = data; // Guarda na memória global
          renderizarTabela(data);
          resultadoDiv.innerHTML = `
            <div class="alert alert-success">
                <i class="fas fa-check-circle"></i> XML lido com sucesso!<br>
                <strong>Fornecedor:</strong> ${data.fornecedor} <br>
                <strong>NF:</strong> ${data.numero} - <strong>Emissão:</strong> ${data.data_emissao || 'N/A'}
            </div>`;
        } else {
          resultadoDiv.innerHTML = `<div class="alert alert-danger"><i class="fas fa-times-circle"></i> ${data.message || "Erro desconhecido"}</div>`;
        }
      } catch (err) {
        console.error(err);
        resultadoDiv.innerHTML = `<div class="alert alert-danger">Erro de comunicação com o servidor.</div>`;
      } finally {
        btnImportar.disabled = false;
        btnImportar.innerHTML = '<i class="fas fa-cloud-upload-alt me-1"></i> Enviar e Processar';
      }
    });
  }

  // Renderiza a pré-visualização
  function renderizarTabela(data) {
    wrapTabela.classList.remove("d-none");
    btnSalvar.classList.remove("d-none");
    
    let html = "";
    let totalQtd = 0;
    let totalValor = 0;

    data.itens.forEach((item, idx) => {
      totalQtd += item.quantidade;
      totalValor += item.valor_total;
      
      // Exibe badge de serial se tiver
      const badgeSerial = item.seriais_xml 
        ? `<span class="badge bg-info text-dark" title="${item.seriais_xml}"><i class="fas fa-barcode"></i> Com Seriais</span>` 
        : '<span class="text-muted">-</span>';

      html += `
        <tr>
          <td>${idx + 1}</td>
          <td>${item.descricao}</td>
          <td>${item.marca || ''}</td>
          <td>${item.modelo || ''}</td>
          <td class="text-center">${badgeSerial}</td>
          <td class="text-end text-nowrap">${item.quantidade}</td>
          <td class="text-end text-nowrap">R$ ${item.valor_unitario.toFixed(2)}</td>
          <td class="text-end text-nowrap fw-bold">R$ ${item.valor_total.toFixed(2)}</td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
    
    // Atualiza resumo
    resumoImport.innerHTML = `
        <strong>Total Itens:</strong> ${data.itens.length} | 
        <strong>Qtd. Peças:</strong> ${totalQtd} | 
        <strong>Valor Total:</strong> R$ ${totalValor.toFixed(2)}
    `;
  }

  // --- LÓGICA DE SALVAR (COM VÍNCULO DE PEDIDO) ---
  if (btnSalvar) {
    btnSalvar.addEventListener("click", async () => {
        if (!window.dadosNF) return;

        // Captura o ID do pedido selecionado
        const selectPedido = document.getElementById("pedido_id");
        if (selectPedido && selectPedido.value) {
            window.dadosNF.pedido_id = selectPedido.value; // Injeta no payload
        }

        btnSalvar.disabled = true;
        btnSalvar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Salvando...';

        try {
            const resp = await fetch("/compras/salvar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(window.dadosNF),
            });

            const res = await resp.json();

            if (res.success) {
                // Redireciona para a Mesa de Recebimento
                window.location.href = `/compras/${res.nf_id}`;
            } else {
                alert("Erro ao salvar: " + res.message);
                btnSalvar.disabled = false;
                btnSalvar.innerHTML = '<i class="fas fa-save me-1"></i> Salvar NF no Sistema';
            }
        } catch (err) {
            console.error(err);
            alert("Erro fatal ao salvar.");
            btnSalvar.disabled = false;
        }
    });
  }
});