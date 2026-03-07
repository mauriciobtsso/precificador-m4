/**
 * M4 TÁTICA - Arsenal Cart Handler
 * Centraliza a lógica AJAX do carrinho e protege o servidor contra spam de cliques.
 */
(() => {
    const cart = {
        debounceTimer: null,
        
        async add(produtoId) {
            // Se o usuário clicar várias vezes, reinicia o timer (Debounce de 150ms)
            clearTimeout(this.debounceTimer);
            
            this.debounceTimer = setTimeout(async () => {
                try {
                    const response = await fetch(`/carrinho/add/${produtoId}`, {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest'
                        }
                    });

                    const data = await response.json();

                    if (data.success) {
                        this.updateUI(data);
                    }
                } catch (error) {
                    console.error('Erro ao comunicar com o Arsenal:', error);
                }
            }, 150);
        },

        updateUI(data) {
            // Atualiza o contador (Badge)
            const badge = document.getElementById('cart-badge');
            if (badge) {
                badge.textContent = data.cart_count;
                badge.classList.remove('d-none');
            }

            // Dispara o alerta visual (Toast)
            const toastEl = document.getElementById('cartToast');
            const msgEl = document.getElementById('toastMessage');
            
            if (toastEl && msgEl) {
                msgEl.textContent = data.message;
                const toast = new bootstrap.Toast(toastEl);
                toast.show();
            }
        }
    };

    // Define a função global que os botões já usam
    window.adicionarAoCarrinho = (id) => cart.add(id);
})();