// ======================
// ARMAS - JS
// ======================

document.addEventListener("DOMContentLoaded", () => {

  // 1) Upload do botão "Enviar e Processar CRAF" (aba armas)
  const uploadForm = document.getElementById("formUploadCraf");
  if (uploadForm) {
    uploadForm.addEventListener("submit", async function (e) {
      e.preventDefault();

      const formData = new FormData(uploadForm);
      const clienteId = uploadForm.dataset.clienteId;

      try {
        const response = await fetch(`/uploads/${clienteId}/craf`, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          throw new Error("Erro no upload do CRAF");
        }

        const dados = await response.json();
        abrirPreverCraf(dados); // abre o modal de pré-visualização
      } catch (err) {
        alert("Erro ao processar CRAF: " + err.message);
      }
    });
  }

  // 2) Upload do CRAF dentro do modal "+ Nova Arma"
  const uploadNovaArma = document.getElementById("uploadNovaArma");
  if (uploadNovaArma) {
    uploadNovaArma.addEventListener("change", async function () {
      const clienteId = document.querySelector("#formUploadCraf")?.dataset.clienteId;
      if (!clienteId) return;

      const file = this.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch(`/uploads/${clienteId}/craf`, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          throw new Error("Erro no upload do CRAF");
        }

        const dados = await response.json();
        preencherModalNovaArma(dados);

      } catch (err) {
        alert("Erro ao processar CRAF: " + err.message);
      }
    });
  }

  // 3) Upload de CRAF dentro dos modais de edição (dinâmicos)
  document.querySelectorAll("[id^='uploadEditarArma']").forEach(input => {
    input.addEventListener("change", async function () {
      const armaId = this.id.replace("uploadEditarArma", "");
      const clienteId = document.querySelector("#formUploadCraf")?.dataset.clienteId;
      if (!clienteId || !armaId) return;

      const file = this.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch(`/uploads/${clienteId}/craf`, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          throw new Error("Erro no upload do CRAF");
        }

        const dados = await response.json();
        preencherModalEditarArma(armaId, dados);

      } catch (err) {
        alert("Erro ao processar CRAF: " + err.message);
      }
    });
  });

});


// ======================
// Funções auxiliares
// ======================

// Pré-visualização no modal "Enviar e Processar CRAF"
function abrirPreverCraf(dados) {
  document.getElementById("crafTipo").value = dados.tipo || '';
  document.getElementById("crafFuncionamento").value = dados.funcionamento || '';
  document.getElementById("crafMarca").value = dados.marca || '';
  document.getElementById("crafModelo").value = dados.modelo || '';
  document.getElementById("crafCalibre").value = dados.calibre || '';
  document.getElementById("crafNumeroSerie").value = dados.numero_serie || '';
  document.getElementById("crafEmissor").value = dados.emissor_craf || '';
  document.getElementById("crafSigma").value = dados.numero_sigma || '';
  document.getElementById("crafCategoria").value = dados.categoria_adquirente || '';
  document.getElementById("crafValidadeIndet").checked = !!dados.validade_indeterminada;

  const validade = dados.data_validade_craf || '';
  if (validade) {
    const parts = validade.split('/');
    if (parts.length === 3) {
      document.getElementById("crafValidade").value =
        `${parts[2]}-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}`;
    }
  } else {
    document.getElementById("crafValidade").value = '';
  }

  document.getElementById("crafCaminho").value = dados.caminho_craf || '';

  var modal = new bootstrap.Modal(document.getElementById('preverCrafModal'));
  modal.show();
}

// Preencher modal "+ Nova Arma" com dados do OCR
function preencherModalNovaArma(dados) {
  const modal = document.getElementById("modalNovaArma");
  if (!modal) return;

  modal.querySelector("select[name='tipo']").value = dados.tipo || "";
  modal.querySelector("select[name='funcionamento']").value = dados.funcionamento || "";
  modal.querySelector("input[name='marca']").value = dados.marca || "";
  modal.querySelector("input[name='modelo']").value = dados.modelo || "";
  modal.querySelector("input[name='calibre']").value = dados.calibre || "";
  modal.querySelector("input[name='numero_serie']").value = dados.numero_serie || "";
  modal.querySelector("select[name='emissor_craf']").value = dados.emissor_craf || "";
  modal.querySelector("input[name='numero_sigma']").value = dados.numero_sigma || "";
  modal.querySelector("select[name='categoria_adquirente']").value = dados.categoria_adquirente || "";

  if (dados.validade_indeterminada) {
    modal.querySelector("input[name='validade_indeterminada']").checked = true;
  }

  if (dados.data_validade_craf) {
    const parts = dados.data_validade_craf.split("/");
    if (parts.length === 3) {
      modal.querySelector("input[name='data_validade_craf']").value =
        `${parts[2]}-${parts[1].padStart(2, "0")}-${parts[0].padStart(2, "0")}`;
    }
  }

  modal.querySelector("input[name='caminho_craf']").value = dados.caminho_craf || "";
}

// Preencher modal "Editar Arma" com dados do OCR
function preencherModalEditarArma(armaId, dados) {
  const modal = document.getElementById("modalEditarArma" + armaId);
  if (!modal) return;

  modal.querySelector("select[name='tipo']").value = dados.tipo || "";
  modal.querySelector("select[name='funcionamento']").value = dados.funcionamento || "";
  modal.querySelector("input[name='marca']").value = dados.marca || "";
  modal.querySelector("input[name='modelo']").value = dados.modelo || "";
  modal.querySelector("input[name='calibre']").value = dados.calibre || "";
  modal.querySelector("input[name='numero_serie']").value = dados.numero_serie || "";
  modal.querySelector("select[name='emissor_craf']").value = dados.emissor_craf || "";
  modal.querySelector("input[name='numero_sigma']").value = dados.numero_sigma || "";
  modal.querySelector("select[name='categoria_adquirente']").value = dados.categoria_adquirente || "";

  if (dados.validade_indeterminada) {
    modal.querySelector("input[name='validade_indeterminada']").checked = true;
  }

  if (dados.data_validade_craf) {
    const parts = dados.data_validade_craf.split("/");
    if (parts.length === 3) {
      modal.querySelector("input[name='data_validade_craf']").value =
        `${parts[2]}-${parts[1].padStart(2, "0")}-${parts[0].padStart(2, "0")}`;
    }
  }

  modal.querySelector("input[name='caminho_craf']").value = dados.caminho_craf || "";
}
