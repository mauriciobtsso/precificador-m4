// clientes.js
// Controle do modal "Adicionar Contato": label dinâmico + máscara de telefone/celular/whatsapp

(function () {
  function aplicarMascara(tipo) {
    var $valor = $("#contatoValor");

    // Remove máscara anterior (se plugin estiver presente)
    if (typeof $valor.unmask === "function") {
      try { $valor.unmask(); } catch (e) {}
    }

    // Ajustes por tipo
    if (tipo === "telefone") {
      $valor.attr("type", "tel");
      $valor.attr("inputmode", "tel");
      $valor.attr("placeholder", "(99) 9999-9999");
      if (typeof $valor.mask === "function") {
        $valor.mask("(00) 0000-0000");
      }
      $valor.removeClass("is-invalid");
    } else if (tipo === "celular" || tipo === "whatsapp") {
      $valor.attr("type", "tel");
      $valor.attr("inputmode", "tel");
      $valor.attr("placeholder", "(99) 99999-9999");
      if (typeof $valor.mask === "function") {
        $valor.mask("(00) 00000-0000");
      }
      $valor.removeClass("is-invalid");
    } else if (tipo === "email") {
      $valor.attr("type", "email");
      $valor.removeAttr("inputmode");
      $valor.attr("placeholder", "exemplo@dominio.com");
    } else {
      $valor.attr("type", "text");
      $valor.removeAttr("inputmode");
      $valor.attr("placeholder", "Digite o contato");
      $valor.removeClass("is-invalid");
    }
  }

  function atualizarLabel(tipo) {
    var $label = $("#contatoValorLabel");
    var texto = "Valor";

    if (tipo === "telefone") texto = "Telefone";
    else if (tipo === "celular") texto = "Celular";
    else if (tipo === "whatsapp") texto = "WhatsApp";
    else if (tipo === "email") texto = "E-mail";

    $label.text(texto);
  }

  function validarEmail(valor) {
    if (!valor) return true;
    var re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(String(valor).toLowerCase());
  }

  function bindEventos() {
    var $tipo = $("#contatoTipo");
    var $valor = $("#contatoValor");

    // Atualiza campo sempre que mudar o tipo
    $tipo.on("change", function () {
      var tipo = $(this).val();
      atualizarLabel(tipo);
      aplicarMascara(tipo);
      $valor.val("").removeClass("is-invalid");
    });

    // Validação leve de e-mail
    $valor.on("blur", function () {
      var tipo = $tipo.val();
      if (tipo === "email") {
        var ok = validarEmail($(this).val());
        $(this).toggleClass("is-invalid", !ok);
      }
    });

    // Inicializa com o estado atual
    var tipoAtual = $tipo.val();
    atualizarLabel(tipoAtual);
    aplicarMascara(tipoAtual);
  }

  // Quando o modal abrir, reconfigura tudo
  $(document).on("shown.bs.modal", "#contatoModal", function () {
    bindEventos();
    $("#contatoTipo").trigger("change"); // força aplicação inicial
  });

  // Se o modal já estiver visível
  $(function () {
    if ($("#contatoModal").is(":visible")) {
      bindEventos();
    }
  });
})();
