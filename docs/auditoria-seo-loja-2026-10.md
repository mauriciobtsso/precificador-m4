# Auditoria SEO da loja M4 Tática

**Atualizada:** 14/10/2026
**Loja:** https://loja.m4tatica.com.br
**Commit da auditoria técnica inicial:** `9c9b6b1`
**Commits desta continuação:** `2428f4f` e `ff749d8`
**Deploy de código:** `dep-db7pqiss728c73dg1pk0`, estado **live**

A loja tem os dez pontos da imagem verificados. Sete estão implementados ou melhorados. O evento de compra está no código, mas a coleta no GA4 depende de validar a tag e o consentimento no GTM. Dois itens de conteúdo continuam pendentes: cases reais e um prazo de resposta que a equipe consiga cumprir.

## Itens verificados

| # | Item | Situação e ação |
|---|---|---|
| 1 | Página 404 personalizada | **Implementada.** Responde com HTTP 404, página em português, busca funcional e `noindex`. Respostas JSON de API continuam em JSON. |
| 2 | CTA acima da dobra | **Implementado.** A home tem H1 e botão “Explorar catálogo” antes do banner. |
| 3 | Links internos | **Melhorados.** Busca tem paginação HTML. Home e rodapé apontam para FAQ. O sitemap lista a FAQ. URLs canônicas usam o domínio público. |
| 4 | Página de obrigado e conversão | **Implementado no código.** A página envia o evento `purchase` ao `dataLayer` somente para pedidos com status pago. Inclui ID da transação, valor, moeda BRL e um item genérico. Não inclui nome, CPF, telefone, e-mail, endereço ou produtos reais. O disparo no GA4 depende da tag e do consentimento configurados no GTM. |
| 5 | Breadcrumbs | **Implementados.** Breadcrumbs visuais e `BreadcrumbList` usam a hierarquia real. A FAQ também tem breadcrumb estruturado. |
| 6 | Cases com resultado | **Pendente.** Não há resultados públicos comprovados. É preciso fornecer números, período e autorização de publicação. |
| 7 | Perguntas frequentes | **Implementadas.** A página pública contém as respostas do anexo do usuário, revisão de conteúdo legal, links oficiais, metadados, breadcrumb e links internos. Não foi adicionado schema `FAQPage`: o Google limita bastante os resultados enriquecidos de FAQ e não garante exibição para lojas comerciais. |
| 8 | Prazo de resposta visível | **Pendente.** Não foi publicada a promessa de resposta em 24 horas. A equipe precisa confirmar que pode cumprir o prazo e informar dias e horários. |
| 9 | CTA fixo no mobile | **Implementado** no detalhe do produto, para telas até 992 px. Inclui tablets e compatibilidade com Safari antigo. |
| 10 | `robots.txt` | **Corrigido na auditoria inicial.** O arquivo aponta para o sitemap XML. `robots.txt` orienta rastreadores; não protege dados privados. |

## O que entrou nesta continuação

### FAQ pública

A nova página está em `/perguntas-frequentes`. Ela responde às perguntas do anexo e aparece na home, no rodapé e no sitemap. A página usa conteúdo HTML do servidor. Não depende de JavaScript para mostrar as respostas.

O preço público foi publicado conforme o material recebido: **R$ 1.600,00 à vista ou 10 parcelas de R$ 184,33**. A resposta sobre aquisição de arma usa as orientações da Polícia Federal. A lista de calibres do anexo não foi copiada como regra vigente, pois existe norma oficial posterior sobre classificação. As respostas legais apontam para as fontes oficiais. Elas não substituem a confirmação dos requisitos atuais com a Polícia Federal.

### Contato por WhatsApp

A página de contato agora monta uma mensagem no navegador e abre o WhatsApp para o cliente revisar e enviar. A loja não recebe essa mensagem pelo servidor. O botão não envia nada automaticamente. Incluí uma validação alternativa para Safari antigo, como o usado no iPad mini 1.

### Evento de compra

A página de confirmação envia `purchase` apenas quando o pedido já está pago. O evento usa um nome genérico para o item e não envia dados pessoais nem nomes de produtos. Também evita repetir o envio na mesma sessão.

O script público do GTM respondeu HTTP 200 e contém referência a uma configuração GA4. Isso não prova que exista uma tag acionada pelo evento `purchase`. Não acessei o painel privado do GTM e não alterei tags. Também não implementei um novo banner nem uma nova política de consentimento. A coleta depende da configuração atual do GTM e do consentimento aplicável.

A regra `Disallow: /carrinho/` continua ativa. Ela impede que o Google leia o `noindex` da página de confirmação. Não removi a regra porque isso permitiria rastreio de rotas de checkout. A decisão sobre essa exceção ainda precisa de aprovação.

## Validação

Depois do deploy, o domínio oficial respondeu HTTP 200 na home, na FAQ, no contato, em `sitemap.xml` e em `robots.txt`. A FAQ estava visível e tinha canonical e `BreadcrumbList`. O sitemap XML era válido e continha a FAQ. O contato mostrava o formulário WhatsApp e o fallback de Safari antigo.

A suíte completa passou: **123 testes**. Também passaram a compilação Python e `git diff --check`. Permaneceu um aviso conhecido do Flask-Limiter: os testes usam armazenamento em memória.

O deploy Docker `dep-db7pqiss728c73dg1pk0`, associado ao commit `ff749d8`, terminou como **live** em `2026-10-14T15:20:03Z`. Nenhum pedido foi criado. Nenhum pagamento foi realizado. Nenhuma mensagem foi enviada pelo WhatsApp. Os testes de conversão usam pedidos sintéticos.

## Próximas ações

1. Confirmar no modo Preview do GTM e no relatório em tempo real do GA4 se `purchase` chega à propriedade. Confirmar também se a tag segue o consentimento configurado.
2. Decidir se o Google pode rastrear `/carrinho/` para ler o `noindex`. Manter o bloqueio evita que o robô visite o checkout, mas também impede a leitura dessa meta tag.
3. Confirmar se a equipe consegue responder em até 24 horas. Se sim, definir dias, horários e exceções antes de publicar o prazo.
4. Enviar cases reais, com período, métricas verificáveis e autorização de publicação.
5. Acompanhar impressões, cliques, CTR e consultas no Google Search Console. O SEO não garante posição específica.

## Fontes oficiais

- [Links rastreáveis](https://developers.google.com/search/docs/crawling-indexing/links-crawlable)
- [Sitemaps XML](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
- [`robots.txt`: função e limites](https://developers.google.com/search/docs/crawling-indexing/robots/intro)
- [Páginas 404 e soft 404](https://developers.google.com/search/blog/2008/08/farewell-to-soft-404s)
- [Dados estruturados de breadcrumb](https://developers.google.com/search/docs/appearance/structured-data/breadcrumb)
- [Políticas de dados estruturados](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)
- [FAQ structured data](https://developers.google.com/search/docs/appearance/structured-data/faqpage)
- [Eventos de e-commerce no GA4](https://developers.google.com/analytics/devguides/collection/ga4/ecommerce)
- [Consentimento e Google tags](https://developers.google.com/tag-platform/security/guides/consent)
- [Polícia Federal — aquisição de arma de fogo](https://www.gov.br/pf/pt-br/assuntos/carta-de-servicos/armas/adquirir-arma-de-fogo)
- [Polícia Federal — legislação de armas](https://www.gov.br/pf/pt-br/assuntos/armas/normativos/legislacao)
- [Instrução Normativa PF nº 201/2021](https://www.gov.br/pf/pt-br/assuntos/armas/normativos/in2012021atualizadadgpf.pdf)
- [Portaria Conjunta C Ex/DG-PF nº 4/2025, Diário Oficial da União](https://www.in.gov.br/en/web/dou/-/portaria-conjunta-c-ex/dg-pf-n-4-de-18-de-julho-de-2025-645587385)
