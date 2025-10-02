// enderecos.js
// Máscaras e regras para formulários/modais de endereços (CEP, número, UF)

(function () {
  function aplicarMascaras($root) {
    // CEP: 00000-000
    var $cep = $root.find("#cep");
    if ($cep.length) {
      if (typeof $cep.unmask === "function") {
        try { $cep.unmask(); } catch (e) {}
      }
      if (typeof $cep.mask === "function") {
        $cep.mask("00000-000");
      }
      $cep.attr({
        "placeholder": "00000-000",
        "inputmode": "numeric",
        "maxlength": "9",
        "autocomplete": "postal-code"
      });
    }

    // Número: apenas dígitos
    var $numero = $root.find("#numero");
    if ($numero.length) {
      $numero.on("input", function () {
        this.value = this.value.replace(/\D/g, "");
      });
      $numero.attr({ "inputmode": "numeric" });
    }

    // UF: 2 letras maiúsculas
    var $uf = $root.find("#estado");
    if ($uf.length) {
      $uf.on("input", function () {
        this.value = this.value.toUpperCase().replace(/[^A-Z]/g, "").slice(0, 2);
      });
      $uf.attr({ "maxlength": "2", "style": "text-transform:uppercase" });
    }
  }

  // Quando abrir o modal de endereço → aplica no conteúdo do modal
  $(document).on("shown.bs.modal", "#modalAddEndereco", function () {
    aplicarMascaras($(this));
  });

  // Caso exista formulário de endereço fora de modal (ex.: página de edição) → aplica no documento
  $(function () {
    if ($("#cep").length) {
      aplicarMascaras($(document));
    }
  });
})();
