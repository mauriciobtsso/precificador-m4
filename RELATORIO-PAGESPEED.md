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
