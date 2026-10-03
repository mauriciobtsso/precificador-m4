

## 02/10/2026 — Cache offline do catálogo para navegação rápida no iPad Mini 1

### Contexto e limitação encontrada

Foi solicitado suporte a Service Worker para permitir navegação instantânea e offline no `/catalogo`. Durante a implementação foi considerada a compatibilidade do equipamento informado: o iPad Mini 1, normalmente limitado ao iOS 9.3.x, não possui suporte a Service Workers. Portanto, somente adicionar `navigator.serviceWorker.register()` não resolveria o problema nesse aparelho.

### Solução implantada

Foi implementado o Service Worker `m4-catalogo-v1`, servido pela própria aplicação em `/catalogo/service-worker.js`, com escopo restrito a `/catalogo/`. O worker pré-carrega o shell do catálogo, a folha reduzida de ícones, fonte, logo, favicon e placeholder. As páginas HTML e assets visitados são armazenados em cache para abertura rápida nas visitas seguintes. APIs de busca e demais endpoints dinâmicos não são interceptados como cache-first, evitando resultados antigos de pesquisa. Em caso de falha de rede, o worker retorna o catálogo em cache para navegação e o placeholder para imagens não disponíveis.

O registro do worker só ocorre quando o navegador oferece `navigator.serviceWorker`, com tratamento silencioso de erro para não prejudicar o funcionamento normal do catálogo. O endpoint envia `Service-Worker-Allowed: /catalogo/` e `Cache-Control: no-cache`, permitindo que novas versões do worker sejam detectadas corretamente.

Para atender especificamente o iPad Mini 1/iOS 9, foi adicionado um fallback AppCache legado. O HTML do catálogo inclui o manifesto somente quando o User-Agent é iPad ou iPhone, evitando ativar AppCache desnecessariamente em navegadores modernos. O manifesto `/catalogo/offline.manifest` mantém em cache o shell e assets leves, permite rede para APIs e proxy de imagens e define fallback para `/catalogo/`.

### Conflitos e decisões

O conflito principal foi entre o requisito de Service Worker e a capacidade real do dispositivo legado. A decisão foi não fingir compatibilidade: navegadores modernos usam Service Worker, enquanto o iPad Mini 1 usa AppCache, que é a alternativa disponível no iOS 9. O escopo foi limitado ao catálogo para não interferir na loja virtual, checkout, APIs de busca ou administração.

Também foi adotada sintaxe ES5 no worker para reduzir riscos em navegadores antigos que eventualmente suportem partes da API, e foram configurados cabeçalhos de atualização para impedir que o próprio arquivo do worker fique preso em cache antigo.

### Validações

A rota do Service Worker, o manifesto e seus cabeçalhos foram testados. O JavaScript do worker passou no `node --check`, o template Jinja foi validado, o manifesto foi validado por estrutura e a suíte completa passou com **70 testes aprovados**. Permaneceu apenas o aviso conhecido do Flask-Limiter sobre armazenamento em memória durante os testes.
