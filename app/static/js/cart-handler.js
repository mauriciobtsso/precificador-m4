/**
 * M4 TÁTICA - Arsenal Cart Handler (ES5 Version)
 * Centraliza a lógica AJAX do carrinho e protege o servidor contra spam de cliques.
 * Compatível com navegadores antigos (iOS 9, etc).
 */
(function() {
    var cart = {
        debounceTimer: null,
        
        add: function(produtoId, btn) {
            var self = this;
            var originalHtml = '';
            
            if (btn) {
                originalHtml = btn.innerHTML;
                btn.disabled = true;
                btn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>AGUARDE...';
            }

            // Se o usuário clicar várias vezes, reinicia o timer (Debounce de 150ms)
            if (this.debounceTimer) {
                clearTimeout(this.debounceTimer);
            }
            
            this.debounceTimer = setTimeout(function() {
                var xhr = new XMLHttpRequest();
                xhr.open('POST', '/carrinho/add/' + produtoId, true);
                xhr.setRequestHeader('Content-Type', 'application/json');
                xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
                
                xhr.onreadystatechange = function() {
                    if (xhr.readyState === 4) {
                        if (btn) {
                            btn.disabled = false;
                            btn.innerHTML = originalHtml;
                        }
                        
                        if (xhr.status === 200) {
                            try {
                                var data = JSON.parse(xhr.responseText);
                                if (data.success) {
                                    self.updateUI(data);
                                }
                            } catch (e) {
                                console.error('Erro ao processar resposta do carrinho:', e);
                            }
                        } else {
                            console.error('Erro ao comunicar com o Arsenal:', xhr.status);
                        }
                    }
                };
                xhr.send();
            }, 150);
        },

        updateUI: function(data) {
            // Atualiza o contador (Badge)
            var badge = document.getElementById('cart-badge');
            if (badge) {
                badge.textContent = data.cart_count;
                badge.className = badge.className.replace(/\bd-none\b/g, '');
            }

            // Dispara o alerta visual (Toast)
            var toastEl = document.getElementById('cartToast');
            var msgEl = document.getElementById('toastMessage');
            
            if (toastEl && msgEl) {
                msgEl.textContent = data.message;
                // Bootstrap 5 Toast (Assume-se que o vendor está carregado)
                if (window.bootstrap && window.bootstrap.Toast) {
                    var toast = new bootstrap.Toast(toastEl);
                    toast.show();
                }
            }
        }
    };

    // Define a função global que os botões já usam
    window.adicionarAoCarrinho = function(id, btn) {
        // Se btn não for passado, tenta pegar do evento global (compatibilidade ES5/Legado)
        var target = btn;
        if (!target && window.event) {
            target = window.event.currentTarget || window.event.srcElement;
            // Se o clique foi no ícone dentro do botão, sobe até o botão
            while (target && target.tagName !== 'BUTTON' && target.tagName !== 'A') {
                target = target.parentNode;
            }
        }
        cart.add(id, target);
    };
})();
