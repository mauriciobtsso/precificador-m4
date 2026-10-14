# Auditoria SEO da loja M4 Tática

**Data:** 14/10/2026  
**Escopo:** loja pública em `https://loja.m4tatica.com.br`  
**Commit de código:** `9c9b6b1`  
**Render:** deploy `dep-db7l3m142hec739at9p0`, estado **live**

## Resumo

A auditoria encontrou problemas técnicos e de conteúdo. As correções técnicas foram implementadas e publicadas. O deploy Docker terminou sem erro.

A verificação pública confirmou:

- Home: HTTP 200, H1 principal e CTA para o catálogo.
- `robots.txt`: HTTP 200, uma declaração válida para o sitemap XML.
- Sitemap: HTTP 200 e XML válido.
- URL inexistente: HTTP 404, página personalizada e `X-Robots-Tag: noindex, follow`.
- Uma categoria e um produto: HTTP 200, uma canonical para o domínio oficial.
- JSON-LD de produto válido. A marcação de avaliação não comprovada foi removida.
- CTA fixo do produto presente para telas de até 992 px. Isso inclui tablets com viewport de 768 px.

O objetivo é melhorar a rastreabilidade, a clareza e a conversão. **Nenhuma alteração garante uma posição específica no Google.** Conteúdo útil, concorrência, autoridade e dados do Search Console também afetam o resultado.

## Auditoria dos dez itens

| # | Item | Estado antes da mudança | Ação e estado atual |
|---|---|---|---|
| 1 | Página 404 personalizada | A URL inexistente retornava HTTP 404, mas sem página visual própria. | **Implementado.** Página em português, pesquisa funcional, link para a loja, status 404 e `noindex`. Respostas 404 de API continuam em JSON quando solicitadas. |
| 2 | CTA acima da dobra | A home pública não tinha H1 semântico visível no primeiro conteúdo. | **Implementado.** H1 curto e botão “Explorar catálogo” antes do banner. O botão leva à seção do catálogo. |
| 3 | Links internos | A navegação interna existia. A busca não oferecia paginação rastreável. | **Melhorado.** A busca agora tem links HTML para as páginas seguintes. O helper de URL usa o host oficial e remove o prefixo interno `/loja`. |
| 4 | Página de obrigado | A tela de pedido concluído existia. O código da aplicação não enviava evento `purchase` ao `dataLayer`. | **Parcial.** A tela recebe `noindex` no HTML e no cabeçalho HTTP. O evento de conversão não foi criado. O GTM está instalado, mas não foi possível inspecionar a configuração interna do container. A regra atual também bloqueia `/carrinho/` em `robots.txt`; assim, o Google não consegue ler a meta tag dessa rota. Mantive o bloqueio para não liberar o rastreio do checkout sem decisão. |
| 5 | Breadcrumbs | Havia marcação de breadcrumb, mas ela podia usar host interno e criar hierarquia incompleta. | **Corrigido.** A marcação só aparece quando há mais de um nível. Os links usam URLs canônicas públicas. Categoria e produto foram verificados ao vivo. |
| 6 | Cases com resultados | Não foram encontrados cases públicos com resultados verificáveis. | **Pendente.** Exige dados reais, autorização de publicação e, se necessário, anonimização. Não inventei resultados. |
| 7 | Cinco perguntas frequentes | Não foi encontrada uma seção pública de FAQ. | **Pendente.** As perguntas e respostas precisam refletir políticas reais. O Google não garante rich results de FAQ para lojas comerciais. Use FAQ primeiro para ajudar visitantes. |
| 8 | Prazo de resposta visível | Não foi encontrada promessa pública de prazo de resposta. | **Pendente.** Não publiquei “retorno em 24h” sem confirmar que a equipe pode cumprir esse prazo. |
| 9 | CTA fixo no mobile | O detalhe de produto não tinha CTA persistente ao rolar a página. | **Implementado.** Barra fixa com preço à vista e botão de carrinho. O breakpoint inclui tablets e usa `bottom/left/right` para compatibilidade com Safari antigo. |
| 10 | `robots.txt` | O arquivo apontava para o sitemap XML e também listava `llms.txt` como se fosse sitemap. | **Corrigido.** Ficou apenas a declaração do sitemap XML. `robots.txt` orienta rastreadores; ele não protege dados nem substitui autenticação. |

## Outras correções técnicas

- Canonicals, Open Graph e URLs de dados estruturados usam `https://loja.m4tatica.com.br`.
- Busca e parâmetros de rastreamento não criam canonical duplicada.
- O sitemap inclui produtos visíveis, categorias com produtos visíveis e páginas institucionais públicas. Exclui categorias vazias e páginas ocultas. O `lastmod` usa a atualização da página ou do produto relacionado.
- Categorias, produtos, páginas institucionais, contato e links úteis recebem títulos e descrições próprios.
- O JSON-LD de produto deixou de declarar avaliação 5/5, estoque sempre disponível, frete grátis, devolução grátis em sete dias e prazos fixos de entrega sem validação comercial. Também saiu a data fixa de validade do preço.
- A página de contato tem um formulário que ainda não funciona: ele envia POST para `#`, não tem nomes de campos e a rota aceita apenas GET. Os canais de WhatsApp, e-mail e endereço aparecem na página. Não troquei o fluxo do formulário por WhatsApp ou e-mail sem autorização.

## Pendências e plano de ação

### Prioridade 1 — medir conversões e corrigir o contato

1. Definir como enviar o formulário de contato: serviço de e-mail, WhatsApp com texto preenchido ou remoção do formulário com manutenção dos canais diretos.
2. Definir o evento GA4 `purchase`, a regra de consentimento e os dados permitidos. Sugestão inicial: não enviar nome, e-mail, telefone ou outros dados pessoais. Confirmar também se os itens comprados podem ser enviados ao Google Analytics.
3. Decidir se `/carrinho/` deve continuar bloqueado para rastreadores. Para o Google processar `noindex`, o robô precisa poder buscar a página. A exceção pode expor a página de confirmação ao crawler. Avaliar isso junto com o evento e a privacidade.

### Prioridade 2 — conteúdo real

1. Aprovar cinco perguntas frequentes e respostas. Cobrir somente políticas confirmadas de pagamento, frete, troca, garantia e canais de atendimento.
2. Confirmar se a equipe pode responder em até 24 horas. Definir horário, dias úteis e exceções antes de exibir a promessa.
3. Enviar um ou mais resultados comprováveis. Informar os números, o período, a autorização de publicação e os dados que devem ser ocultados.

### Prioridade 3 — acompanhar o efeito

1. Conferir propriedade e sitemap no Google Search Console.
2. Acompanhar cobertura, consultas, impressões, cliques e CTR por página.
3. Comparar períodos equivalentes. Ajustar titles, descrições e conteúdo com base nos termos reais.

## Validação

- **119 testes aprovados**. `py_compile` e `git diff --check` passaram.
- A suíte mantém um aviso conhecido do Flask-Limiter: o ambiente de teste usa armazenamento em memória.
- Não acessei pedidos, contas de clientes nem configurações internas do GTM.
- Não enviei dados do formulário e não criei cases, perguntas, prazos ou avaliações fictícias.

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
