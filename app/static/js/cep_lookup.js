// =============================
// CEP LOOKUP + MÁSCARA AUTOMÁTICA (versão segura p/ todas as páginas)
// =============================
function initCepLookup() {
  const cepInput = document.querySelector("input[name='cep']");
  if (!cepInput) {
    console.warn("Campo CEP não encontrado.");
    return;
  }

  // --- Máscara de CEP ---
  cepInput.addEventListener("input", (e) => {
    let v = e.target.value.replace(/\D/g, "");
    if (v.length > 5) v = v.slice(0, 5) + "-" + v.slice(5, 8);
    e.target.value = v;
  });

  // --- Consulta ViaCEP ao sair do campo ---
  cepInput.addEventListener("blur", async () => {
    const cep = cepInput.value.replace(/\D/g, "");
    if (cep.length !== 8) return;

    try {
      cepInput.classList.add("is-loading");

      const resp = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
      if (!resp.ok) throw new Error("Erro ao buscar CEP");

      const data = await resp.json();
      if (data.erro) {
        alert("CEP não encontrado!");
        return;
      }

      const setValue = (name, val) => {
        const el = document.querySelector(`input[name='${name}']`);
        if (!el) return;
        // se o valor anterior veio de outro CEP, atualiza
        if (!el.dataset.lastCep || el.dataset.lastCep !== cep) {
          el.value = val || "";
          el.dataset.lastCep = cep;
        }
      };

      setValue("endereco", data.logradouro);
      setValue("bairro", data.bairro);
      setValue("cidade", data.localidade);
      setValue("estado", data.uf);
    } catch (err) {
      console.error("Erro ao buscar CEP:", err);
      alert("Não foi possível buscar o CEP.");
    } finally {
      cepInput.classList.remove("is-loading");
    }
  });
}

// --- Executa ao carregar DOM ---
// Repetição garante compatibilidade com includes renderizados depois
document.addEventListener("DOMContentLoaded", () => {
  initCepLookup();
  // fallback extra: tenta de novo após 500ms
  setTimeout(initCepLookup, 500);
});
