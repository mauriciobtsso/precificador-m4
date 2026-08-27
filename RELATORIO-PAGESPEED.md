# Relatório de otimização PageSpeed e SEO

## Escopo

Foi analisado o relatório do PageSpeed Insights da loja pública `https://loja.m4tatica.com.br/`, gerado em 26/08/2026, juntamente com o código do repositório `mauriciobtsso/precificador-m4`. A intervenção foi concentrada na vitrine pública, nos cards de produtos, nos recursos críticos de carregamento, nos metadados de SEO e nos headers HTTP.

## Diagnóstico de referência

| Indicador | Resultado no relatório |
|---|---:|
| Desempenho Lighthouse | 83 |
| LCP de campo | 4,3 s |
| FCP de campo | 3,9 s |
| TTFB de campo | 3,6 s |
| CLS de campo | 0 |
| LCP de laboratório | 4,0 s |
| CSS não utilizado estimado | 42,4 KiB |
| Erro de proxy de imagem | HTTP 400 em `wsrv.nl` |
| Miniatura ausente | HTTP 404 em `_t280.webp` |
| CSP | Ausente |
| SEO Lighthouse | 100 |

## Correções implementadas

| Área | Implementação |
|---|---|
| Imagens | Remoção das chamadas ao proxy externo que retornava HTTP 400. Cards e autocomplete agora usam URL CDN estável; fallback passou a ser um placeholder local garantido. As dimensões `width`, `height` e a reserva quadrada do container foram preservadas para manter CLS zero. |
| LCP | O logo público usa preload de WebP e mantém PNG como fallback para navegadores sem suporte. O primeiro banner continua com `fetchpriority="high"`, dimensões explícitas e carregamento eager. |
| HTML | O CSS do card, antes repetido a cada produto incluído, foi extraído para `app/static/css/loja-card.css` e carregado uma única vez. Isso reduz HTML duplicado e parsing do navegador. |
| Ícones | Foi criada uma folha reduzida com os 55 ícones efetivamente usados pela loja em `bootstrap-icons-loja.css`, reduzindo a folha CSS de 93.733 para 3.225 bytes. A fonte original foi preservada. |
| TTFB | A consulta de `destaques` que não era renderizada na home foi removida. A chave do cache da home passou a variar por URL e `loja_cliente_id`, evitando resposta personalizada compartilhada entre sessões. |
| SEO | A descrição específica da home passou a usar o bloco correto (`seo_meta`). Canonical e Open Graph agora usam `request.base_url`, sem query string. URLs hardcoded de `app.m4tatica.com.br` foram substituídas por `url_for` no JSON-LD, e o logo social inexistente foi substituído por `logo.webp`. |
| Segurança | CSP compatível com os CDNs e scripts atuais, HSTS de um ano em HTTPS, COOP `same-origin-allow-popups`, Permissions-Policy, frame protection, referrer policy e MIME protection. HTTPS não é forçado na aplicação porque continua terminado no proxy. |
| Confiabilidade | Corrigida a chamada incompatível do helper no autocomplete. Também foram corrigidos fixtures/testes legados para refletir o contrato atual do formulário de produtos e manter a suíte executável em banco SQLite isolado. |

## Validação executada

A compilação Python, a verificação de whitespace e a suíte completa foram executadas com sucesso:

```text
17 passed, 1 warning in 1.23s
```

Os testes novos verificam ausência dos proxies quebrados e do asset inexistente, SEO dinâmico, cobertura dos ícones reduzidos, variação segura do cache, fallback local de imagens, renderização real da home pública e presença de CSP/HSTS/COOP. O único aviso restante é do Flask-Limiter usando armazenamento em memória durante testes.

## Entrega

As alterações foram commitadas e enviadas para a branch `main`:

```text
535f091 perf: otimizar loja pública e corrigir SEO
```

## Validação pós-publicação recomendada

Após o deploy automático ou manual, deve-se executar novamente o PageSpeed para a URL pública em janela anônima, em mobile e desktop. Também é importante confirmar no HTML publicado que não existem ocorrências de `wsrv.nl`, `logo-social.png` ou `app.m4tatica.com.br/loja`, verificar no DevTools que não há respostas 400/404 nos recursos da home e medir novamente TTFB, LCP e FCP. A mudança de imagens removeu o dimensionamento externo dinâmico do proxy; se a equipe desejar reduzir ainda mais o peso das imagens de produto, o próximo passo seguro é executar um backfill controlado das miniaturas ausentes no bucket público e então reintroduzir `srcset` somente com variantes comprovadamente existentes.


## Segundo reteste mobile — 27/08/2026

O novo relatório foi analisado em captura vertical de alta resolução, em simulação de Moto G Power com 4G lento. O resultado atual mostra **Performance 71**, FCP de **0,9 s**, LCP de **2,3 s**, TBT de **170 ms**, Speed Index de **1,4 s** e CLS de **1,282**. Acessibilidade, práticas recomendadas e SEO permanecem em **100**.

| Evidência do reteste | Causa identificada |
|---|---|
| Economia potencial de 919 KiB | Cards e banners ainda baixavam originais de 1.080–1.499 px para áreas menores |
| CLS de 1,282 | `main#main-content` contribuía com 0,987 e a fonte Bootstrap Icons com 0,294 |
| GTM com 283,8 KiB e 211 ms de tarefas longas | Analytics ainda competia com o carregamento inicial |
| CSS não utilizado de 30 KiB e JS não utilizado de 131 KiB | Recursos globais e GTM eram avaliados no carregamento inicial |
| Dois cards com `loading=eager`/`fetchpriority=high` | Prioridade alta estava sendo aplicada além do elemento LCP |
| Banners sem variante menor | `srcset` anterior declarava somente uma URL de 1200w |

## Correções adicionais executadas

| Área | Implementação da segunda rodada |
|---|---|
| Imagens responsivas | O proxy público local `/catalogo/image-proxy/...` agora aceita `w` e `q`, redimensiona a imagem no servidor com Pillow, entrega WebP para navegadores compatíveis e JPEG como fallback, e usa cache por caminho, largura, qualidade e formato. |
| Cards | Cards passaram a usar `srcset` real de 160w/280w, `sizes` responsivo, `loading="lazy"` e fallback original apenas se o proxy falhar. A prioridade alta foi removida da home e das categorias. |
| Banner LCP | O banner passou a usar variantes de 640w/1200w no `srcset` e no preload, mantendo a prioridade alta apenas no primeiro banner. |
| Marcas e busca | Logos de marcas e imagens do autocomplete passaram a usar o mesmo proxy dimensionado, sem depender de `_t80.webp` possivelmente ausente. |
| CLS | A reserva de proporção do hero foi movida para o CSS crítico do head, o `content-visibility` do hero foi removido e cada ícone ganhou caixa mínima de 1em para evitar mudança de largura quando a fonte carregar. Bootstrap, ícones e CSS dos cards passaram a ser aplicados antes da renderização do layout. |
| GTM | O carregamento foi postergado para 10 segundos após `load` ou 350 ms após interação real, evitando que o gerenciador dispute a primeira pintura; o rastreamento continua disponível sem bloquear a navegação. |
| Página de detalhe | A imagem principal também passou a usar variantes 800w/1200w, `sizes` e a mesma área previamente reservada de 600 px. |
| Cache e compatibilidade | Foi corrigida a resolução da instância do Flask-Caching e acrescentado `Vary: Accept`, evitando respostas WebP/JPEG incorretamente reutilizadas por caches intermediários. |

## Validação da segunda rodada

Foram executados compilação Python, `git diff --check`, testes unitários e testes de integração do endpoint público. Resultado:

```text
22 passed, 1 warning in 1.59s
```

A validação integrada confirmou resposta 200 do proxy com imagem WebP redimensionada, proporção preservada, cache público e `Vary: Accept`. O único aviso continua sendo o armazenamento em memória do Flask-Limiter no ambiente de testes.

## Validação pós-deploy atualizada

Depois da publicação da nova branch, deve-se repetir o PageSpeed em mobile e desktop. No DevTools, a verificação principal é confirmar que os cards requisitam URLs `/catalogo/image-proxy/...?...w=160` ou `w=280`, que o banner seleciona 640w em viewport móvel, que as respostas têm tamanho significativamente menor que as originais e que não há 400/404. Também deve-se confirmar no relatório que o CLS caiu substancialmente e que GTM deixou de aparecer entre as tarefas longas do carregamento inicial.
