# Registro de manutenções da aplicação M4 Tática

## Contexto

Foi corrigido o fluxo de promoções usado no cadastro de produtos, na listagem administrativa (`/produtos`) e na loja pública. O problema afetava tanto a persistência das datas informadas no formulário quanto a atualização do preço exibido depois do término da promoção.

## Causa raiz

A rota de criação/edição salvava o preço promocional e o indicador de ativação, mas não atribuía os campos `promo_data_inicio` e `promo_data_fim` recebidos pelo formulário. Consequentemente, as datas não eram persistidas quando o produto era salvo manualmente.

Além disso, o autosave recebia os valores do input HTML `datetime-local` como strings no formato `YYYY-MM-DDTHH:MM` e atribuía essas strings diretamente às colunas `DateTime`. Não havia conversão para um `datetime` com o fuso horário da aplicação.

Por fim, a listagem administrativa renderizava `produto.preco_a_vista`, que é um valor persistido e pode ter sido calculado enquanto a promoção estava ativa. Assim, mesmo quando a vigência já havia terminado, a tela podia continuar mostrando o valor antigo. A listagem também mantinha fragmentos em cache, o que prolongava a exibição do HTML anterior.

## Correção implementada

Foi criado `app/utils/parsing.py`, com conversões centralizadas para valores monetários brasileiros e para datas locais. O parser monetário aceita, por exemplo, `R$ 2.050,00`, e o parser de data interpreta os valores de `datetime-local` no fuso `America/Fortaleza`, armazenando-os com informação explícita de fuso.

A rota de produto agora persiste `promo_data_inicio` e `promo_data_fim`, inclui todos os campos de promoção na auditoria e usa o parser monetário compartilhado. O autosave passou a converter as datas antes de atribuí-las ao modelo, inclusive no autosave em lote.

O cálculo de preços agora normaliza valores de data vindos do banco antes da comparação com o horário atual. A promoção é considerada ativa somente quando o instante atual está entre início e fim, inclusive nos limites; após o instante final, o custo promocional deixa de ser aplicado.

A listagem administrativa recalcula o preço efetivo no momento da renderização, utiliza o resultado para o valor e para o badge da promoção e deixou de reutilizar fragmentos cacheados para evitar HTML promocional vencido. A loja pública já chamava `calcular_precos()` na renderização e passa a se beneficiar das datas persistidas e da comparação temporal normalizada.

## Validações executadas

Foram executados os seguintes comandos:

- `python3 -m py_compile app/utils/parsing.py app/produtos/models.py app/produtos/routes/main.py app/produtos/routes/autosave.py`
- `git diff --check`
- `pytest -q tests/test_promocoes.py` — **4 testes aprovados**
- `pytest -q` — **32 testes aprovados e 1 falha preexistente**, relacionada à folha reduzida de ícones da loja (`bi-google` e `bi-star-fill`), sem relação com a correção de promoções.

Os novos testes cobrem a conversão de `R$ 2.050,00`, a interpretação do horário local, a aplicação da promoção durante a janela e a desativação imediatamente após o término.

## Entrega

A alteração foi preparada para commit e envio na branch `main` do repositório `mauriciobtsso/precificador-m4`.

## Nova tarefa planejada — Links úteis

Será implementada uma área pública de **Links úteis** na loja, com acesso discreto pelo rodapé, e uma área administrativa para cadastrar, editar, excluir, ordenar e controlar a publicação desses links. Cada link poderá ter título, URL, resumo opcional e status de publicação. A página pública será responsiva, organizada e visualmente consistente com o design atual da loja; resumos vazios não serão renderizados nem exibidos como `None`.

## Links úteis — execução concluída

Foi criada a tabela `loja_links_uteis`, com migração Alembic `b7c4d91f2a10_criar_links_uteis_da_loja.py`. O modelo suporta título, URL, resumo opcional, ordem de exibição, status de publicação e timestamps.

Na administração da loja, foram adicionados o menu lateral, o indicador no dashboard e o CRUD completo em `/admin-loja/links-uteis`. É possível criar, editar, publicar, ocultar, ordenar e excluir links. URLs externas são validadas para aceitar somente `http://` e `https://`; caminhos internos iniciados por `/` também são aceitos. Resumos são normalizados para `NULL` quando vazios.

Na loja pública, foi criada a página `/loja/links-uteis`, que no modo de vitrine pública fica disponível em `/links-uteis`. A página exibe somente registros ativos, ordenados pelo campo configurado, abre links externos em nova aba e possui layout responsivo com cards alinhados ao visual escuro e dourado da M4 Tática. O acesso foi incluído discretamente no bloco “Conteúdo” do rodapé. A rota também foi adicionada ao sitemap público da loja. O template público condiciona a renderização do resumo ao seu preenchimento; portanto, resumos vazios não geram texto, `None` ou espaços reservados visíveis.

**Homologação de Segurança (CSRF):** Durante a fase de testes, os formulários `POST` de criação (`/admin-loja/links-uteis/novo`) e exclusão (`/admin-loja/links-uteis/excluir/<id>`) apresentaram erro `400 Bad Request`. A correção foi aplicada cirurgicamente injetando a tag invisível `csrf_token()` nos respectivos templates HTML, garantindo a validação antifraude imposta pela camada global do Flask-WTF sem alterar a lógica de controle.

### Validação da funcionalidade de links úteis

- `pytest -q tests/test_links_uteis.py` — **2 testes aprovados**.
- `python3 -m py_compile app/loja/models_admin.py app/loja/routes.py app/loja_admin/routes.py migrations/versions/b7c4d91f2a10_criar_links_uteis_da_loja.py` — aprovado.
- `git diff --check` — aprovado.
- Verificação do grafo de migrações — `b7c4d91f2a10` identificado como head único.


## 24/09/2026 — Correção do detalhe e impressão de pedidos da loja

### Solicitação
Ajustar `/admin-loja/pedidos` e o detalhe do pedido para exibir código do produto, item e quantidade; disponibilizar impressão do pedido e da etiqueta de envio; e reduzir a tipografia do painel para evitar scroll horizontal.

### Alterações realizadas
- Corrigida a iteração dos produtos no detalhe: o modelo `Pedido` expõe a relação `items`, enquanto o template utilizava `itens`; por isso a tabela aparecia sem os itens e mostrava somente os totais.
- Mantidos e destacados na tabela o nome do produto, código, quantidade, preço unitário e subtotal.
- Adicionados os botões **Imprimir pedido** e **Imprimir etiqueta** no detalhe, abrindo as versões próprias em nova aba.
- Criada a rota protegida `/admin-loja/pedidos/<id>/imprimir` e seu template com cliente, endereço, pagamento, itens, códigos, quantidades e totais.
- Criada a rota protegida `/admin-loja/pedidos/<id>/etiqueta` e seu template em formato de etiqueta 100 × 150 mm, com destinatário, endereço, CEP e número do pedido.
- Reduzida a fonte base do painel, da navegação, tabelas e cabeçalhos; adicionados `min-width: 0` e controle de overflow horizontal no layout administrativo, preservando a rolagem interna de tabelas quando necessário em telas estreitas.
- Adicionados testes de regressão para a relação correta dos itens, dados exibidos, rotas/templates de impressão e regras de layout.

### Validações
- `python3 -m py_compile app/loja_admin/routes.py` — aprovado.
- `pytest -q tests/test_loja_admin_pedidos.py` — executado após a implementação.
- `git diff --check` — executado antes do commit.

### Entrega
Alterações commitadas e enviadas para a branch `main` do repositório `mauriciobtsso/precificador-m4`.


## 24/09/2026 — Formatação brasileira dos valores dos pedidos

A lista, o detalhe e a impressão dos pedidos deixavam os valores com ponto decimal e sem separador de milhares, como `R$ 143.71` e `R$ 13288.55`. Os templates administrativos passaram a utilizar o filtro global `currency`, que apresenta os valores no padrão brasileiro, como `R$ 143,71` e `R$ 13.288,55`, incluindo preços unitários, subtotais, frete e totais.

A persistência foi mantida corretamente como dado monetário numérico nas colunas `Numeric(12, 2)` do modelo `Pedido`. O fluxo de criação agora converte os totais para `Decimal`, arredonda para duas casas com `ROUND_HALF_UP` e só então grava `total_produtos`, `total_frete` e `total_pedido`. Assim, o banco não recebe o texto formatado `R$ ...`; a formatação brasileira é aplicada na apresentação, preservando cálculos, filtros e integrações.

Foram adicionados testes para assegurar o uso do filtro BRL nas telas de pedidos e a quantização Decimal antes da persistência. Os testes específicos passaram com 6 aprovações; também foram executados compilação Python e `git diff --check` com sucesso.


## 29/09/2026 — Correção do valor parcelado nos cards da loja

No card de produtos de `/loja`, o texto de 12x era calculado simplesmente dividindo o preço à vista por 12. Essa regra ignorava a taxa de juros cadastrada para parcelamento e podia exibir um valor menor do que o apresentado no detalhe do produto, no modal “Ver todas as formas de parcelamento”.

Foi adicionado um helper compartilhado ao contexto da loja que carrega as taxas cadastradas e reutiliza `gerar_linhas_parcelas`, exatamente como o detalhe do produto. O card principal e o card alternativo agora exibem a parcela da linha `12x` calculada com a taxa vigente no banco. O fallback antigo `precos.preco_a_vista / 12` foi removido.

Foram adicionados testes para confirmar que a taxa de 12x é aplicada e que ambos os cards reutilizam o mesmo cálculo do detalhe.


## 29/09/2026 — Taxas exclusivas para o parcelamento da loja

### Solicitação e escopo
Separar as taxas exibidas pela vitrine pública dos parâmetros usados pelos fluxos internos, disponibilizar gerenciamento em `/admin-loja/taxas-link` e atualizar cards, detalhe e modal da `/loja` sem alterar o módulo interno `/taxas`.

### Alterações realizadas
- Criado o modelo `TaxaLojaLink`, mapeado para `taxas_loja_link`, com unicidade por quantidade de parcelas e juros independentes.
- Adicionada a migração Alembic `20260929_taxas_link`, descendente da revisão `b7c4d91f2a10`. Na implantação, a tabela é inicializada com uma cópia das taxas existentes; em caso de duplicidade legada por quantidade de parcelas, é preservado deterministicamente o registro de menor ID. A tabela `taxas` e as taxas internas não são alteradas.
- Criado o CRUD administrativo protegido por autenticação em `/admin-loja/taxas-link`, com inclusão, edição e exclusão via POST, validação de parcelas (0 a 36, sendo 0 débito), juros (0% a 100%) e duplicidade. Adicionado o acesso no menu lateral e no dashboard de `/admin-loja`.
- Cards da loja e cálculo de parcelamento do detalhe/modal passaram a consultar somente `TaxaLojaLink`. O cálculo compartilhado de linhas de parcelamento foi mantido; nenhum fluxo administrativo/interno de taxas foi redirecionado para a nova tabela.
- Adicionada invalidação versionada e persistida em configuração própria para as respostas cacheadas da home, categorias e detalhe, além das opções de parcelamento por produto. Criar, editar ou excluir uma taxa atualiza a versão na mesma transação, evitando exibição de parcelas antigas inclusive entre workers da aplicação.
- Adicionados testes para isolamento em relação à tabela interna, cálculo independente, rotas/cache versionado e presença de CSRF nos formulários.

### Validações
- `python3 -m py_compile` nos módulos, migração e testes alterados — aprovado.
- `pytest -q` — **48 testes aprovados**; permaneceu apenas o aviso de configuração em memória do Flask-Limiter.
- Ensaio da migração em SQLite com uma tabela `taxas` contendo uma faixa duplicada — aprovado; a nova tabela recebeu uma única taxa por faixa, preservando o registro de menor ID, e a tabela original permaneceu intacta.
- Grafo Alembic — `20260929_taxas_link` confirmado como head único, descendente de `b7c4d91f2a10`.
- `git diff --check` — aprovado.


## 29/09/2026 — Etapa 2: snapshot financeiro do checkout público e PIX

### Implementação

- Adicionada a revisão Alembic `20260929_pix_snapshot`, dependente de `20260929_taxas_link`, com os campos nullable de snapshot (`total_cobrado`, `taxa_aplicada`, `desconto_aplicado` e `valor_parcela`), chave única `checkout_key` e dados do QR Code PIX. Pedidos antigos preservam os valores e exibem fallback para `total_pedido`.
- O checkout público agora calcula os valores em `Decimal` com arredondamento monetário `ROUND_HALF_UP`, registra no pedido o total-base (`total_pedido`), o desconto e o valor final efetivamente enviado ao Pagar.me. A oferta PIX existente foi implementada como **5% de desconto sobre os produtos; o frete permanece sem desconto**. Para PIX, `parcelas=1`, `taxa_aplicada=0` e `valor_parcela=total_cobrado`.
- A integração cria pedidos no Pagar.me Core v5 em modo PIX, usa a chave secreta já configurada em Admin Loja → Integrações e persiste o identificador, código copia-e-cola, URL do QR e vencimento retornados pelo gateway. O payload não contém dados de cartão.
- O endpoint `POST /carrinho/webhook/pagarme` consulta o pedido diretamente na API autenticada do Pagar.me antes de atualizar status; também confere ID, código público e valor contra o snapshot local. Assim, o conteúdo do POST de webhook não é tratado como prova suficiente de pagamento.
- A chave única do checkout evita cobranças repetidas em reenvios e respostas ambíguas. A submissão do pagamento passou a exigir CSRF. A seleção de frete recebe assinatura HMAC com validade de 15 minutos e vinculada à composição do carrinho, impedindo reduzir o preço pelo navegador; limpar frete é uma operação separada.
- Cartão permanece bloqueado tanto na interface quanto no servidor até confirmar se a conta Pagar.me é Gateway ou PSP. E-mails, listagens, detalhes e impressão do pedido distinguem valor-base, desconto e total cobrado; a tela de sucesso mostra o QR real e código copia-e-cola.

### Configuração operacional

O checkout PIX requer a chave `integ_pagarme_secret_key` em **Admin Loja → Integrações**. Para atualizar os status e recuperar QR Code quando uma resposta da criação for ambígua, configure no painel do Pagar.me o endpoint público `POST /carrinho/webhook/pagarme` e os eventos de pedido suportados (`order.created`, `order.paid`, `order.payment_failed` e `order.canceled`). A implementação valida cada evento consultando a API autenticada. Não foi feita chamada de cobrança real durante os testes; estes usam respostas simuladas. Pagamento por cartão segue indisponível até confirmar o tipo da conta e o fluxo seguro apropriado.

### Validações

- `pytest -q`: **59 testes passaram** (1 aviso do Flask-Limiter sobre armazenamento de rate limit em memória no teste).
- `py_compile` nos módulos Python e `git diff --check`: concluídos sem erro.
- Grafo Alembic: head único `20260929_pix_snapshot`, encadeado à revisão `20260929_taxas_link`.
- Migração testada isoladamente em SQLite: `upgrade` e `downgrade` aprovados, incluindo o índice único da chave de checkout.


## 30/09/2026–01/10/2026 — Galeria de fotos dos produtos na loja pública

### Solicitação e escopo

Permitir o cadastro de mais de uma foto por produto, possibilitar a definição de uma foto principal e exibir todas as fotos no detalhe público da loja. O escopo incluiu o formulário administrativo de produtos e a página pública de detalhe.

### Implementação persistente

- Criado o modelo `ProdutoFoto` em `app/produtos/models.py`, relacionado a `Produto` pela relação `fotos`, com URL, ordem, indicador de principal, timestamp e exclusão em cascata.
- Mantido o campo legado `Produto.foto_url` como espelho da foto principal para preservar integrações, templates e registros antigos.
- Criada a migração Alembic `20260930_produto_fotos.py`, descendente de `20260929_pix_snapshot`, criando a tabela `produto_fotos`, índices de produto/principal/ordem e migrando automaticamente a foto existente de `produtos.foto_url` para a nova galeria.
- Atualizado o cadastro administrativo para aceitar múltiplos arquivos, mostrar miniaturas, remover fotos e selecionar exatamente uma foto principal.
- O fluxo de salvamento manual sincroniza a galeria, mantém a ordem, move imagens temporárias para a pasta definitiva do produto no R2 e atualiza `foto_url` com a principal.
- O detalhe público passou a carregar `Produto.fotos` com `subqueryload`, renderizar a imagem principal, exibir miniaturas e trocar a imagem via JavaScript sem recarregar a página.
- O JSON-LD do produto passou a listar todas as imagens disponíveis.

### Erros e conflitos encontrados

1. **Galeria não persistia ao trocar de aba ou sair do cadastro**

   O JavaScript enviava o campo `fotos_produto`, mas o endpoint de autosave em `app/produtos/routes/autosave.py` ignorava esse campo porque ele não era uma coluna direta de `Produto`. A tela mostrava as fotos, porém o autosave descartava a alteração.

   **Solução implantada:** o autosave passou a interpretar o JSON da galeria, comparar o estado atual com o recebido, recriar a relação `ProdutoFoto`, atualizar a foto principal e registrar a alteração no histórico.

2. **Rota pública usada no diagnóstico estava com prefixo incorreto**

   O blueprint possui o prefixo `/loja` no ambiente interno, mas o domínio público `loja.m4tatica.com.br` publica a loja na raiz. Portanto, o endereço canônico do detalhe é `/produto/<slug>`. A tentativa em `/loja/produto/<slug>` retornou `404` no domínio público, enquanto o endereço sem `/loja` retornou `200`.

   **Solução/registro operacional:** validar o detalhe público sempre pelo endereço canônico:
   `https://loja.m4tatica.com.br/produto/<slug>`.

3. **Miniaturas presentes no HTML, mas visualmente cobertas durante a rolagem**

   A imagem principal usava `position: sticky` e permanecia sobreposta ao conteúdo durante a rolagem e em capturas de página inteira. O print enviado mostrou a imagem principal cobrindo a região onde deveriam aparecer as miniaturas, apesar de o HTML conter as fotos.

   **Solução implantada:** removido o comportamento `sticky`, definida posição normal/relativa para o contêiner da imagem e adicionada altura mínima/padding à faixa `.produto-galeria-thumbs`, mantendo as miniaturas claramente visíveis abaixo da imagem principal.

4. **Cache e atualização do código público**

   O detalhe utilizava cache de 300 segundos e a chave anterior não distinguia explicitamente a nova versão visual. Após a correção, o domínio ainda entregou temporariamente o CSS antigo com `position: sticky`, mesmo com o commit já publicado no GitHub.

   **Solução implantada:** incrementado o namespace da chave de cache do detalhe de `v4` para `v5`, incluindo também o timestamp de atualização do produto. Foi identificado que o repositório não possui workflow GitHub Actions de deploy; por isso, o push na `main` e o redeploy do provedor são etapas distintas. Após o redeploy, a correção passou a funcionar na página pública.

5. **Compatibilidade com produtos antigos**

   Produtos sem registros em `produto_fotos` poderiam ficar sem imagem se o template dependesse somente da nova relação.

   **Solução implantada:** o template usa fallback para `produto.foto_url` quando a galeria ainda está vazia, e a migração também popula a nova tabela a partir das fotos legadas.

### Commits entregues

- `52030b5` — `feat: adicionar galeria de fotos aos produtos`
- `7ea0f9a` — `fix: persistir galeria de fotos no autosave`
- `4e9f658` — `fix: manter miniaturas visiveis no detalhe da loja`
- `38bf1c6` — `fix: exibir galeria sem sobreposicao no detalhe publico`

Todos os commits foram enviados para a branch `main` do repositório `mauriciobtsso/precificador-m4`.

### Validações executadas

- `python3 -m py_compile` nos modelos, rotas de produtos, autosave, rota da loja e migração — aprovado.
- `node --check app/static/js/produtos_form.js` — aprovado.
- Parsing dos templates Jinja do cadastro e do detalhe — aprovado.
- `git diff --check` — aprovado.
- Verificação pública do produto Taurus GX2 — HTML contendo duas miniaturas e duas URLs de fotos.
- Inspeção com navegador automatizado — galeria visível, duas miniaturas presentes e clicáveis.
- Verificação pós-deploy — miniaturas renderizadas abaixo da imagem principal após a atualização do serviço público.

### Resultado final

O cadastro permite adicionar várias fotos e escolher a principal. A loja pública exibe a imagem principal e miniaturas navegáveis no detalhe do produto. A foto principal continua sincronizada com o campo legado, produtos antigos permanecem compatíveis e o cache do detalhe é invalidado quando a galeria é atualizada.


## 01/10/2026 — Mensagem pública do PIX e desconto configurável

### Solicitação e problema identificado

No checkout público da loja, quando a chave secreta do Pagar.me não estava configurada, o cliente via a mensagem interna:

> O PIX está indisponível até configurar a chave secreta do Pagar.me em Admin Loja → Integrações.

Além disso, o checkout aplicava automaticamente um desconto fixo de 5% no PIX. Essa regra não dava autonomia à loja para decidir se o desconto deveria existir nem qual percentual deveria ser aplicado.

### Alterações implantadas

- Removida do checkout público a exposição de detalhes técnicos sobre chave secreta, Pagar.me e caminho administrativo.
- Substituída a mensagem por uma orientação apropriada ao cliente:
  > O pagamento via PIX está temporariamente indisponível. Tente novamente mais tarde ou fale com nossa equipe.
- O desconto PIX deixou de ser fixo em 5% e passou a ter padrão **desativado, com 0%**.
- Adicionada a função `obter_desconto_pix_percentual()` em `app/carrinho/payment.py`, que:
  - só aplica desconto quando a configuração está explicitamente ativa;
  - aceita percentuais de 0% a 100%;
  - retorna 0% para configuração ausente, inválida ou fora do limite;
  - mantém o frete fora da base de desconto.
- `calcular_snapshot_pix()` passou a receber o percentual como parâmetro e a guardar no snapshot o campo `desconto_percentual`, além do valor monetário efetivamente abatido.
- A prévia do checkout e o processamento efetivo do pedido passaram a usar a mesma configuração persistida, evitando que o total apresentado ao cliente seja diferente do total enviado ao gateway.
- Quando o desconto está desativado, o checkout não exibe linha de desconto nem afirma que existe uma promoção. Quando está ativo, exibe o percentual configurado.
- A linha de JavaScript que atualiza o frete foi protegida para funcionar também quando a linha de desconto não é renderizada.

### Autonomia no painel administrativo

Na tela **Admin Loja → Integrações → Pagamento**, foi criado o bloco **Desconto para pagamento via PIX**, com:

- chave de ativação/desativação `loja_pix_desconto_ativo`;
- percentual configurável `loja_pix_desconto_percentual`;
- validação administrativa entre 0% e 100%;
- aceitação de vírgula ou ponto na entrada decimal;
- armazenamento normalizado com duas casas decimais.

As duas chaves também foram adicionadas aos defaults de `Configuracao`, com os valores seguros `0` e `0.00`. Não foi necessária nova migração, pois o projeto já utiliza a tabela genérica `configuracoes`.

### Erros, conflitos e soluções

1. **Desconto fixo hardcoded em vários pontos**

   O percentual de 5% estava definido em `payment.py`, refletido no template do checkout e coberto por testes que assumiam o valor fixo.

   **Solução:** centralizado o percentual no banco de configurações, com padrão zero, parâmetro explícito no cálculo e testes separados para o comportamento padrão e para uma configuração ativa.

2. **Risco de divergência entre prévia e pedido final**

   A tela calculava o snapshot no endpoint de visualização e o serviço recalculava o snapshot no POST de processamento.

   **Solução:** ambos os fluxos consultam `obter_desconto_pix_percentual()` no momento do cálculo. O pedido persiste o desconto monetário efetivamente usado no snapshot.

3. **Linha de desconto ausente causando erro no JavaScript**

   Ao desativar o desconto, a linha `desconto_pix_display` deixa de existir no HTML, mas o JavaScript ainda tentava atualizar o elemento ao selecionar um frete.

   **Solução:** atualização protegida por verificação de existência do elemento.

4. **Suíte de testes inicialmente indisponível no sandbox**

   O comando `pytest` não estava instalado e, na tentativa seguinte, faltava `SQLAlchemy`. As dependências declaradas em `requirements.txt` foram instaladas somente no ambiente de validação do sandbox, sem alteração de dependências do projeto.

5. **Falha não relacionada na suíte completa**

   Os testes específicos do PIX passaram integralmente: **13 testes aprovados**. A suíte completa terminou com **60 testes aprovados e 1 falha** em `tests/test_pagespeed_regressions.py::test_detail_page_uses_responsive_image_delivery`, que ainda espera o texto `imagem_otimizada(url_detalhe_original, 1200)` no detalhe público. Essa expectativa pertence à validação anterior de entrega responsiva da galeria e não foi causada pelas alterações de checkout/desconto desta manutenção.

### Validações

- `python3 -m py_compile` nos módulos Python alterados — aprovado.
- `git diff --check` — aprovado.
- Parsing Jinja de `checkout.html` e `integracoes.html` — aprovado.
- `python3 -m pytest -q tests/test_checkout_pix.py` — **13 aprovados**, com apenas o aviso já conhecido do Flask-Limiter sobre armazenamento em memória nos testes.
- `python3 -m pytest -q` — **60 aprovados e 1 falha não relacionada**, descrita acima.
- Busca de textos antigos — nenhuma mensagem técnica sobre chave secreta/Admin Loja permaneceu no checkout público e nenhuma descrição fixa de 5% permaneceu na aplicação pública.

### Resultado final

O cliente não vê mais detalhes internos de configuração quando o PIX está indisponível. O desconto PIX não é mais aplicado automaticamente. A loja pode ativá-lo ou desativá-lo e definir o percentual diretamente em **Admin Loja → Integrações**, com o padrão seguro de desconto desativado.




## 01/10/2026 — Fase 1 da galeria aprimorada no detalhe público da loja

### Objetivo

Evoluir a galeria de fotos em `/loja/produto/<slug>` para oferecer uma experiência mais completa no desktop e no celular, sem alterar o modelo de dados da galeria já implantada.

### Funcionalidades implantadas

- **Imagem principal responsiva** com `srcset` de 800px e 1200px e `sizes` adequado para desktop/mobile.
- Correção da expectativa de entrega responsiva que ainda faltava no detalhe: a versão de 1200px agora é efetivamente utilizada.
- **Contador de fotos** na imagem principal e no visualizador ampliado, no formato `1 / N`.
- **Setas anterior/próxima** na imagem principal quando o produto possui mais de uma foto.
- **Miniaturas aprimoradas**, com:
  - destaque visual mais claro para a foto ativa;
  - foco acessível via teclado;
  - rolagem horizontal no mobile;
  - `aria-current` e rótulos com posição e total de fotos.
- **Lightbox em tela cheia** ao clicar na imagem principal, com:
  - fundo escuro;
  - imagem em alta resolução;
  - botão de fechar;
  - fechamento ao clicar fora da imagem;
  - contador;
  - setas de navegação.
- **Zoom no lightbox** ao clicar na imagem ampliada, com alternância entre escala normal e 1.8x.
- **Navegação por teclado** no lightbox:
  - `Esc` fecha;
  - `ArrowLeft` exibe a foto anterior;
  - `ArrowRight` exibe a próxima foto.
- **Navegação por swipe** na área principal da galeria, com suporte a arrastar horizontalmente no celular.
- Preservação do **fallback para `foto_url` legado** quando o produto não possui registros na nova galeria.
- Preservação do carregamento prioritário da primeira imagem e carregamento lazy das miniaturas.
- Suporte a `prefers-reduced-motion` para reduzir transições quando essa preferência estiver ativa.
- Adicionados ao subconjunto de ícones público os codepoints de `chevron-left`, `chevron-right`, `x-lg` e `zoom-in`, evitando controles visualmente quebrados.

### Erros, conflitos e soluções

1. **O detalhe tinha apenas troca básica por miniatura**

   A implementação anterior trocava apenas o `src` da imagem ao clicar na miniatura. Não havia modal, zoom, setas, contador ou swipe.

   **Solução:** criada uma camada de estado no JavaScript com índice ativo, navegação circular, sincronização entre imagem principal, miniaturas e lightbox.

2. **A imagem principal usava somente a versão de 800px**

   O teste de Pagespeed já esperava a versão de 1200px, mas o template não a utilizava no detalhe.

   **Solução:** adicionados `srcset` com 800w/1200w, `sizes="(max-width: 991px) 100vw, 58vw"` e carregamento da versão grande no lightbox.

3. **Ícones novos ausentes no CSS reduzido da loja**

   A folha `bootstrap-icons-loja.css` é um subconjunto e não continha os quatro ícones necessários para as setas, fechamento e indicação de zoom. O teste de cobertura de ícones detectou o conflito.

   **Solução:** consultados os codepoints do CSS completo local e adicionados somente os quatro ícones ao subconjunto público.

4. **Compatibilidade com produto sem fotos ou com foto legada**

   O lightbox e os controles poderiam aparecer sem imagem ou quebrar em produtos antigos.

   **Solução:** o markup do lightbox só é renderizado quando há foto; a lista continua usando `produto.fotos` com fallback para `produto.foto_url`.

5. **Interação mobile sem dependência de biblioteca adicional**

   Não foi adicionada dependência externa para carrossel ou zoom.

   **Solução:** implementada navegação com Pointer Events, teclado e JavaScript nativo, mantendo o bundle da loja enxuto.

### Testes e validações

- `python3 -m py_compile tests/test_pagespeed_regressions.py` — aprovado.
- Parsing Jinja do template do detalhe — aprovado.
- `node --check` do JavaScript extraído do template — aprovado.
- `git diff --check` — aprovado.
- `python3 -m pytest -q tests/test_pagespeed_regressions.py tests/test_taxas_loja_link.py` — **18 aprovados**.
- `python3 -m pytest -q` — **62 aprovados**, com apenas o aviso já conhecido do Flask-Limiter sobre armazenamento em memória nos testes.
- Cobertura de ícones da loja — aprovada após incluir os quatro codepoints necessários.

### Resultado final

O detalhe público do produto agora permite ampliar a foto, navegar pelas imagens usando miniaturas, setas, teclado e swipe, visualizar a imagem em alta resolução com zoom e acompanhar a posição atual na galeria. A implementação permanece compatível com produtos antigos e mantém a entrega responsiva otimizada para desktop e celular.

### Situação de publicação após o commit

O commit `33c78e2` foi enviado com sucesso para `origin/main`. Na verificação imediatamente posterior e após três novas consultas com intervalo de 10 segundos, a URL pública respondeu HTTP 200, porém ainda entregou o HTML anterior sem `produtoLightbox`, `produtoGaleriaContador` e URLs `w=1200`. Isso indica que o provedor de hospedagem ainda não havia concluído o redeploy/propagação do commit, e não uma falha nos testes ou no código versionado. A funcionalidade está pronta na branch `main` e deve aparecer no domínio assim que o serviço concluir a atualização.

## 01/10/2026 — Fase 2 da galeria: zoom avançado e vídeos dos produtos

### Objetivo

Ampliar a experiência da galeria pública em `/loja/produto/<slug>` com zoom avançado nas fotos e suporte a vídeos cadastrados por produto, mantendo o fallback de produtos antigos e a compatibilidade com a galeria de fotos já existente.

### Implementações realizadas

A estrutura de dados ganhou a entidade `ProdutoVideo`, relacionada a `Produto`, com URL, título opcional, ordem e data de criação. Foi criada a migração reversível `20261001_produto_videos.py`, encadeada após `20260930_produto_fotos`, com índice por produto e ordem.

O cadastro administrativo agora possui uma seção de vídeos separada da seção de fotos. O usuário pode selecionar múltiplos arquivos, acompanhar o upload, visualizar cada vídeo com controles nativos, informar um título opcional, remover itens e salvar a ordem atual. São aceitos MP4, WebM e MOV, com limite de 100 MB por arquivo.

O upload usa o mesmo bucket público R2/CDN da galeria. Vídeos enviados durante o cadastro de um produto novo ficam inicialmente em `produtos/videos/temp/` e são movidos para `produtos/videos/<produto_id>/` após o produto receber seu ID. O autosave e o salvamento tradicional sincronizam títulos e ordem dos vídeos com o banco.

No detalhe público, os vídeos aparecem abaixo das miniaturas, em cartões responsivos com `controls`, `playsinline`, `preload="metadata"` e legenda opcional. A CSP da loja recebeu `media-src` restrito a origens HTTPS, `self` e `blob`, permitindo a reprodução do CDN sem liberar mídia insegura.

O zoom da Fase 1 foi evoluído para aceitar níveis de 1x a 3.5x, roda do mouse, botões de aumentar/reduzir/resetar, duplo clique, atalhos de teclado (`+`, `-` e `0`) e arraste da imagem ampliada para panorâmica. O zoom é redefinido ao trocar de foto ou navegar no lightbox.

### Erros, conflitos e soluções

1. **O modelo anterior contemplava somente fotos.** Foi criada uma relação independente `ProdutoVideo`, evitando misturar URLs de vídeo com `ProdutoFoto` e preservando a foto principal legada em `Produto.foto_url`.

2. **O cadastro tradicional e o autosave tinham fluxos separados.** O payload `videos_produto` foi integrado aos dois caminhos, com normalização de títulos, ordem estável e sincronização transacional.

3. **Produtos novos ainda não têm ID no momento do upload.** O upload utiliza uma pasta temporária e o salvamento move os objetos para a pasta definitiva após o `flush()` do produto, atualizando as URLs persistidas para o CDN.

4. **Browsers podem enviar `application/octet-stream` para arquivos MOV.** A validação aceita somente extensões de vídeo permitidas e normaliza o MIME para `video/quicktime`, evitando que o objeto seja armazenado com Content-Type inadequado.

5. **A política CSP não declarava `media-src`.** Sem a diretiva, a reprodução externa poderia depender de `default-src` e ser bloqueada ou ficar ambígua. Foi adicionada uma diretiva explícita para HTTPS, `self` e `blob`.

6. **O CSS reduzido de ícones não continha os controles da Fase 2.** Foram adicionados os codepoints de câmera de vídeo, menos, tela cheia e os demais controles usados pela nova interface, mantendo o subconjunto público enxuto.

### Testes e validações

- Compilação Python dos modelos, rotas, migração, CSP e testes — aprovada.
- Parsing Jinja dos templates administrativo e público — aprovado.
- `node --check` do JavaScript administrativo e do JavaScript embutido do detalhe — aprovado.
- `git diff --check` — aprovado.
- Testes direcionados de Pagespeed, produtos e loja — **22 aprovados**.
- Suíte completa — **64 aprovados**, com apenas o aviso já conhecido do Flask-Limiter sobre armazenamento em memória nos testes.
- Validação específica de MIME e modelo `ProdutoVideo` — aprovada.

### Resultado final

A Fase 2 permite administrar vídeos junto às fotos do produto, persistir essa mídia com segurança no R2/CDN e exibi-la no detalhe público. As fotos passaram a oferecer zoom avançado com panorâmica, múltiplos níveis de ampliação e controles acessíveis, sem alterar o comportamento de produtos legados.


## 01/10/2026 — Fase 3 da galeria: tour 360 e acessórios relacionados

### Objetivo

Ampliar o detalhe público de `/loja/produto/<slug>` com uma visualização interativa de produto em 360 graus e permitir que a administração selecione acessórios compatíveis para exibição dedicada na loja.

### Implementações realizadas

- Criada a entidade `ProdutoTour360`, com:
  - um tour por produto;
  - título opcional;
  - lista ordenada de frames em JSON;
  - controle de ativação;
  - timestamps de criação e atualização.
- Criada a tabela de associação `produto_acessorios`, permitindo vincular vários produtos como acessórios de outro produto sem duplicar dados.
- Criada a migração reversível `20261001_tour360_acessorios.py`, encadeada após `20261001_produto_videos`, com chaves estrangeiras, índices e unicidade de um tour por produto.
- Adicionado upload administrativo de frames JPG, PNG e WebP, com limite de 15 MB por frame.
- Frames enviados para produto novo são armazenados temporariamente em `produtos/tours360/temp/` e migrados para `produtos/tours360/<produto_id>/` após o produto receber seu ID.
- O cadastro administrativo agora permite:
  - adicionar múltiplos frames;
  - visualizar miniaturas;
  - remover frames;
  - reordenar frames com controles anterior/próximo;
  - selecionar acessórios em uma lista múltipla.
- O autosave e o salvamento tradicional sincronizam o tour 360 e os acessórios selecionados.
- O detalhe público exibe o tour 360 somente quando há pelo menos dois frames e o tour está ativo.
- O tour público permite:
  - arrastar horizontalmente para girar;
  - usar setas de navegação;
  - usar `ArrowLeft` e `ArrowRight` quando o controle estiver focado;
  - acompanhar o contador de frames atual.
- A seção **Acessórios compatíveis** aparece antes das recomendações automáticas e exibe somente acessórios que também estejam visíveis na loja.
- Foram adicionados ao CSS reduzido da loja os ícones necessários para o tour e a seção de acessórios.

### Erros, conflitos e soluções

1. **A aplicação possuía fotos e vídeos, mas nenhum conceito de tour 360.**

   Reutilizar `ProdutoFoto` ou `ProdutoVideo` misturaria mídias com finalidades diferentes e dificultaria a ordenação dos frames.

   **Solução:** criada a entidade independente `ProdutoTour360`, com frames ordenados e relação um-para-um com o produto.

2. **Ainda não existia vínculo manual entre um produto e seus acessórios.**

   As recomendações existentes eram automáticas por categoria e não permitiam controlar compatibilidade comercial.

   **Solução:** criada a associação many-to-many `produto_acessorios`, com seleção administrativa e filtragem pública por `visivel_loja`.

3. **Produtos novos não possuem ID no momento do upload.**

   Assim como ocorreu com as mídias anteriores, o destino definitivo não poderia ser montado antes do primeiro salvamento.

   **Solução:** frames novos utilizam a pasta temporária e são copiados para a pasta definitiva após o `flush()` do produto, antes do commit.

4. **A ordem dos frames é essencial para a sensação de giro contínuo.**

   Apenas armazenar várias URLs sem controles de ordem permitiria que o tour fosse exibido fora de sequência.

   **Solução:** o cadastro mostra miniaturas numeradas e controles para mover cada frame para frente ou para trás; a ordem é enviada no JSON persistido.

5. **A consulta pública poderia gerar consultas extras e mostrar acessórios ocultos.**

   Tour, vídeos, fotos e acessórios são relações diferentes, e nem todo produto relacionado deve aparecer na vitrine.

   **Solução:** a rota usa carregamento antecipado das relações da galeria e filtra os acessórios por `visivel_loja` antes de renderizar.

6. **O cache do detalhe precisava reconhecer mudanças na nova configuração.**

   A página pública já usa a chave baseada em `Produto.atualizado_em`.

   **Solução:** toda alteração de tour ou acessórios atualiza `Produto.atualizado_em`, invalidando a resposta cacheada sem criar uma segunda estratégia de cache.

7. **O comando de inspeção de heads do Alembic não funcionou neste sandbox.**

   O ambiente de execução não tinha `SQLALCHEMY_DATABASE_URI` definida.

   **Solução:** a migração foi validada por compilação Python, encadeamento textual com a revisão anterior e suíte automatizada; a aplicação de banco deve ser executada no ambiente que possui a configuração de banco real.

### Testes e validações

- Compilação Python de modelos, rotas, migração e testes — aprovada.
- Parsing Jinja do detalhe público — aprovado.
- `node --check` do JavaScript administrativo — aprovado.
- `git diff --check` — aprovado.
- Cobertura de ícones da loja — aprovada, sem ícones ausentes.
- Verificação dos modelos no metadata SQLAlchemy — aprovada.
- Testes direcionados de galeria, loja e produtos — **23 aprovados**.
- Suíte completa — **65 aprovados**, com apenas o aviso já conhecido do Flask-Limiter sobre armazenamento em memória nos testes.

### Resultado final

A Fase 3 permite cadastrar e administrar um tour 360 por produto e exibi-lo no detalhe público com navegação natural por arraste, teclado e setas. Também permite definir acessórios compatíveis manualmente, apresentando-os em uma seção própria da loja, sem perder as recomendações automáticas existentes ou a compatibilidade com produtos antigos.


## 01/10/2026 — Correção do upload do tour 360 bloqueado por CSRF

### Problema observado

Ao editar o produto `426` e selecionar frames para o tour 360, o navegador registrava `POST /produtos/api/upload_tour360_frame 400`. Em seguida, o JavaScript apresentava `Unexpected token '<', "<!doctype ..." is not valid JSON`. Também foi observado `POST /produtos/autosave/426 400`.

### Diagnóstico

A aplicação utiliza proteção CSRF global. O formulário administrativo já possuía o campo `csrf_token`, mas os `fetch()` usados pelo upload do tour, pelos uploads de fotos e vídeos e pelo autosave não enviavam o valor no cabeçalho `X-CSRFToken`. O servidor devolvia a página HTML de erro da proteção CSRF, e o código tentava executar `response.json()` sobre esse HTML.

O `404` da imagem antiga registrada no log é independente do erro do tour: trata-se de uma referência de foto legada inexistente no armazenamento público e não é a causa do `400` do upload.

### Soluções implantadas

- Adicionado o envio de `X-CSRFToken` nos uploads de fotos, vídeos e frames do tour 360.
- Adicionado o envio de `X-CSRFToken` no endpoint de autosave.
- Criado leitor de resposta segura no JavaScript do formulário:
  - interpreta JSON quando o servidor retorna JSON;
  - identifica redirecionamento ou HTML de erro;
  - exibe mensagem orientando recarregar a página quando a sessão ou o token expirarem;
  - evita o erro técnico `Unexpected token '<'` no navegador.
- Mantida a proteção CSRF ativa; não foi necessário isentar o novo endpoint.

### Validações

- `node --check app/static/js/produtos_form.js` — aprovado.
- `node --check app/static/js/produtos_autosave.js` — aprovado.
- Verificação de `X-CSRFToken` nos três uploads e no autosave — aprovada.
- `git diff --check` — aprovado.


## 02/10/2026 — Galeria de fotos no detalhe do catálogo legado

### Problema

O detalhe em `/catalogo/produto/<slug>` carregava somente `Produto.foto_url`, embora o cadastro já permitisse várias fotos relacionadas em `Produto.fotos`. Em dispositivos antigos, como o iPad Mini 1 com WebKit/iOS antigo, o cliente não conseguia visualizar as demais imagens do produto.

### Solução implantada

A rota do catálogo passou a carregar `Produto.fotos` com `subqueryload`, respeitando a ordenação existente da relação, que prioriza a foto principal. O template agora monta uma galeria com a foto principal, miniaturas, contador e setas anterior/próxima. Produtos legados sem registros em `Produto.fotos` continuam usando `Produto.foto_url` como fallback.

A implementação visual foi feita com técnicas compatíveis com o navegador antigo: `float`, `inline-block`, botões HTML simples, `var`, `addEventListener`, `classList`, `getAttribute` e navegação por códigos de tecla. Não foi introduzida dependência de CSS Grid, `const`, `let` ou APIs modernas obrigatórias no fluxo da galeria. O cliente pode tocar em uma miniatura, usar as setas, deslizar para aplicar o zoom já existente e usar as setas esquerda/direita do teclado.

As miniaturas utilizam o proxy de imagem com tamanho reduzido (`t160`) para preservar desempenho no iPad, enquanto a imagem principal utiliza a URL otimizada do catálogo. A funcionalidade foi mantida separada do detalhe moderno em `/loja`, sem alterar seus controles avançados.

### Validações

- Parsing Jinja do template — aprovado.
- JavaScript renderizado com expressões Jinja substituídas — aprovado com `node --check`.
- Teste específico da galeria legada — aprovado.
- Suíte completa — **66 testes aprovados**, com apenas o aviso já conhecido do Flask-Limiter sobre armazenamento em memória nos testes.
- `git diff --check` — aprovado.

Uma checagem inicial de compatibilidade acusou falso positivo porque o comentário explicativo continha a expressão `aspect-ratio`; a implementação da galeria não depende dessa propriedade. A validação foi corrigida para verificar o JavaScript efetivo e passou.


## 02/10/2026 — Navegação e ajuste visual da home do catálogo no iPad

### Problemas observados

Na área `/catalogo`, o clique na logo levava para a home da loja virtual (`/loja`) em vez de retornar à home do catálogo. Também foi observado no iPad Mini que o cabeçalho ficava carregado, as categorias formavam uma faixa horizontal cortada e a home tinha espaçamento excessivo entre busca, filtros e produtos.

### Soluções implantadas

O link da logo foi corrigido para apontar para `catalogo.index`, com rótulo acessível indicando o início do Catálogo. Para manter o acesso à loja virtual, foi incluído um botão separado “Loja virtual” no cabeçalho, apontando explicitamente para `loja.index`.

O layout da home foi reorganizado para reduzir o espaço vertical do hero, ampliar a busca principal e alinhar o conteúdo à esquerda em telas de tablet. Os filtros de categoria passam a quebrar em múltiplas linhas a partir de 720px, evitando a sensação de conteúdo cortado no iPad. As imagens dos cards receberam altura definida, além do `aspect-ratio`, para manter dimensões consistentes em navegadores antigos que não suportam essa propriedade. Também foram reduzidos os espaçamentos entre seções.

As alterações preservam as técnicas de compatibilidade com iOS antigo: flexbox com prefixos WebKit, margens reais em vez de `gap`, controles com tamanho mínimo para toque e sem dependência de APIs modernas obrigatórias.

### Validações

- Parsing Jinja dos templates base e índice — aprovado.
- JavaScript dos templates após substituição das expressões Jinja — aprovado com `node --check`.
- Testes estáticos de navegação e layout — aprovados.
- Suíte direcionada de regressões — **18 testes aprovados**.
- `git diff --check` — aprovado.


## 02/10/2026 — Desempenho do catálogo no iPad Mini 1 e navegação por toque

### Contexto e auditoria

O `/catalogo` é usado presencialmente para consultar rapidamente produtos com o cliente. A auditoria identificou que já existiam algumas medidas positivas: proxy local de imagens com conversão automática para JPEG quando o navegador não aceita WebP, cache público das imagens por 30 dias, redimensionamento sob demanda por largura, thumbnails na busca, CSS com prefixos WebKit, layout por `float` no detalhe e navegação básica por miniaturas.

O principal gargalo era compatibilidade: o iPad Mini 1/iOS 9 não entende `loading="lazy"` como lazy loading real. Assim, mesmo com o atributo presente, a home podia iniciar o download das imagens dos três blocos SSR — destaques, lançamentos e promoções — totalizando até 24 imagens. Além disso, os cards usavam thumbnails fixas `t280`, que podiam cair em fallback mais pesado, e o catálogo carregava a folha completa de Bootstrap Icons, aproximadamente 92 KB, embora utilizasse poucos ícones.

No detalhe, a foto principal era requisitada sem largura redimensionada e as miniaturas seguintes também ficavam sujeitas a fallback de imagem grande. A galeria tinha toque para zoom, mas ainda não possuía swipe horizontal confiável para trocar fotos.

### Medidas implantadas

#### Home `/catalogo`

- Implementado lazy loading próprio compatível com iOS 9 usando `data-src`, cálculo de proximidade da viewport e eventos de scroll/resize com agendamento; não depende de `IntersectionObserver` nem do suporte nativo a `loading="lazy"`.
- Somente as três primeiras imagens de destaques são carregadas imediatamente; lançamentos, promoções e demais cards entram progressivamente quando se aproximam da viewport.
- Cards passaram a utilizar `convert_resized_url(..., 220)`, entregando uma imagem dimensionada ao uso real em vez de depender apenas do sufixo de thumbnail.
- Resultados carregados por filtro de categoria também usam o lazy loading próprio.
- Fallback de erro da home foi simplificado para o placeholder local, evitando uma segunda tentativa pesada com a imagem original.
- O context processor deixou de consultar configurações `loja_%` sem uso no catálogo e só carrega categorias quando o endpoint é a home `catalogo.index`. Isso evita consultas repetidas no detalhe do produto.
- O catálogo passou a usar `bootstrap-icons-loja.css`, o subconjunto reduzido já existente, com os cinco codepoints adicionais necessários (`bag`, `grid-fill`, `heart-fill`, `share` e `tag-fill`). O asset CSS caiu de aproximadamente 92 KB para 4 KB.

#### Detalhe do produto no catálogo

- A foto principal passou a ser servida por `convert_resized_url(..., 760)`, reduzindo a transferência sem perder qualidade útil para a coluna de apresentação.
- Miniaturas passaram a usar largura 96 e carregamento sob demanda; apenas a primeira miniatura é solicitada no carregamento inicial.
- A faixa de miniaturas agora é horizontal, sem quebra, com `overflow-x: auto`, `-webkit-overflow-scrolling: touch` e alvos de toque maiores de 72–76 px.
- Ao trocar a foto, a miniatura ativa é automaticamente mantida visível no carrossel horizontal, inclusive quando o cliente navega pelas setas.
- Implementado swipe horizontal na imagem principal: arrastar para a esquerda avança, arrastar para a direita volta; movimentos verticais continuam permitindo a rolagem normal da página.
- Mantidos o duplo toque para zoom, setas e teclado, com listeners sem a opção `passive`, preservando compatibilidade com WebKit antigo.
- Foi definida altura explícita para a área principal da galeria, mantendo o layout estável em navegadores que não suportam `aspect-ratio`.

### Conflitos e ajustes durante a implementação

- A primeira validação do JavaScript encontrou um arquivo temporário antigo de inspeção em `/tmp`, que ainda continha Jinja não renderizado (`{{ produto.id }}`). O arquivo foi removido e a validação passou a gerar nomes temporários limpos a cada execução.
- O teste inicial do swipe procurava o texto `deltaX >= 45`, mas a implementação usa corretamente `Math.abs(deltaX) >= 45` para aceitar arrastes nos dois sentidos. O teste foi corrigido para validar a condição real.
- O editor encontrou três blocos idênticos de fallback de imagem na home e recusou um patch ambíguo. A alteração foi aplicada em lote com assertiva de que exatamente três ocorrências seriam substituídas, evitando mudanças acidentais.
- O teste de ícones confirmou que o subconjunto reduzido não tinha todos os ícones do catálogo; os cinco codepoints ausentes foram adicionados antes da troca do asset.

### Validações

- Parsing Jinja dos templates base, índice e detalhe — aprovado.
- `py_compile` das rotas e testes — aprovado.
- `node --check` dos três scripts extraídos dos templates — aprovado.
- Auditoria dos ícones usados contra o subconjunto reduzido — nenhum ícone ausente.
- Testes direcionados — **21 aprovados**.
- Suíte completa — **68 aprovados**, com apenas o aviso já conhecido do Flask-Limiter sobre armazenamento em memória nos testes.
- `git diff --check` — aprovado.

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

## 05/10/2026 — Correção das fotos dos cards na home do `/catalogo` no iPad Mini 1
### Sintoma observado
Na home do catálogo, as fotos dos cards não carregavam ou permaneciam no placeholder. Ao abrir uma categoria, as imagens carregavam em quantidade significativamente maior. O comportamento foi reportado especificamente no iPad Mini 1/iOS 9.

### Diagnóstico
A comparação do HTML e das rotas encontrou uma regressão introduzida na otimização anterior: a home SSR usava `convert_resized_url(..., 220)`, que faz redimensionamento sob demanda no proxy Flask (`/catalogo/image-proxy/...?...w=220`). Já a API das categorias usava `convert_thumb_url(..., 't280')`, apontando para thumbnails pré-geradas. Assim, a home disparava várias conversões/downloads simultâneos pelo backend, enquanto as categorias usavam o caminho leve já validado.

Além disso, o fallback da home havia sido reduzido diretamente ao placeholder, sem uma segunda tentativa pela imagem original. Se uma thumbnail não existisse ou falhasse, o card ficava definitivamente sem a foto.

### Solução implantada
- Os três blocos SSR da home — Destaques, Últimos Cadastrados e Promoções — passaram a usar `convert_thumb_url(p.foto_url, 't280')`, alinhando o fluxo com as categorias.
- Foi adicionado fallback progressivo: em erro da thumbnail, o navegador tenta `convert_image_url(p.foto_url)` e somente depois usa o placeholder local.
- O lazy loading legado por `data-src`, eventos de scroll/resize e carga inicial das imagens próximas foi preservado, mantendo compatibilidade com iOS 9.
- O comportamento de imagens da API de categorias não foi alterado.

### Conflitos e solução
O editor encontrou três blocos SSR com linhas idênticas e recusou patches sem contexto exclusivo. A alteração foi aplicada bloco a bloco, com contexto das seções Destaques, Últimos Cadastrados e Promoções. O fallback restante foi substituído em lote com assertiva de exatamente duas ocorrências, evitando alterações fora da home.

### Validações
- Template Jinja da home — compilado com sucesso.
- A home não contém mais `convert_resized_url(p.foto_url, 220)`.
- Os três blocos usam thumbnail `t280` e fallback da imagem original.
- `pytest -q tests/test_pagespeed_regressions.py` — **21 testes aprovados**.
- `git diff --check` — aprovado.

## 05/10/2026 — Correção das fotos no detalhe do produto do `/catalogo`
### Sintoma observado
O detalhe do produto apresentava o mesmo comportamento da home: a foto principal ou as miniaturas podiam permanecer no placeholder, especialmente no iPad Mini 1/iOS 9, embora a navegação por categorias carregasse imagens normalmente.

### Diagnóstico
A galeria do detalhe ainda usava `convert_resized_url` com redimensionamento sob demanda para a foto principal (`w=760`) e para as miniaturas (`w=96`). Esse caminho exigia novas conversões pelo proxy Flask. Além disso, o fallback JavaScript da troca de foto usava `data-original`, que pode ser uma URL WebP do CDN e não é exibível nativamente pelo iOS 9.

### Solução implantada
- A foto principal passou a ser carregada pelo `convert_image_url`, que mantém o proxy de compatibilidade e entrega JPEG para navegadores sem suporte a WebP.
- As miniaturas passaram a usar o thumbnail pré-gerado `t280`, o mesmo caminho validado na home e nas categorias.
- Cada miniatura passou a guardar uma URL compatível em `data-fallback`.
- O fallback da troca de fotos agora tenta `data-fallback` antes de considerar a URL original, evitando depender diretamente do WebP no iPad Mini 1.
- Zoom, swipe, setas, teclado e a navegação horizontal das miniaturas foram preservados.

### Validações
- Template Jinja do detalhe compilado com sucesso.
- Removidas da galeria as URLs `convert_resized_url(..., 760)` e `convert_resized_url(..., 96)`.
- `pytest -q tests/test_pagespeed_regressions.py` — **21 testes aprovados**.
- `git diff --check` — aprovado.

## 05/10/2026 — Vídeos do produto via YouTube na `/loja`
### Objetivo
Reduzir o consumo de banda e o armazenamento no R2 para vídeos demonstrativos, permitindo que o cliente assista ao vídeo sem sair da página pública do produto.

### Implementação
- Criado `app/utils/youtube.py` com validação de hosts e extração de IDs para links `youtube.com`, `youtu.be`, Shorts, Embed e Live.
- Links válidos são normalizados para `https://www.youtube.com/watch?v=ID`.
- O player público usa `youtube-nocookie.com` e somente é criado após o cliente clicar na prévia (`loading=lazy`), evitando carregar o player do YouTube na abertura da página.
- A prévia usa a thumbnail pública do vídeo e mantém o vídeo dentro do detalhe da `/loja`.
- Vídeos antigos hospedados no R2 continuam funcionando com o elemento HTML `<video>`.
- O cadastro administrativo ganhou campo para adicionar link do YouTube, título opcional e prévia; o upload de MP4/WebM/MOV foi preservado como alternativa legada.
- O salvamento normal e o autosave aplicam a mesma normalização e bloqueiam URLs externas arbitrárias.
- O ícone `bi-youtube` foi incluído na folha reduzida de Bootstrap Icons da loja.

### Segurança e compatibilidade
- Não é aceito domínio externo como vídeo legado, mesmo que tente imitar o caminho `produtos/videos/`.
- O embed utiliza `rel=0` e `modestbranding=1`.
- Não há autoplay automático; a reprodução começa somente por ação do cliente.
- Títulos e múltiplos vídeos continuam suportados.

### Validações
- `pytest -q tests/test_pagespeed_regressions.py` — **23 testes aprovados**.
- `node --check app/static/js/produtos_form.js` — aprovado.
- Templates Jinja da loja e do formulário administrativo — compilados com sucesso.
- `git diff --check` — aprovado.

## 05/10/2026 — Refinamento visual dos vídeos YouTube
### Ajustes solicitados
O bloco de vídeos do formulário administrativo ocupava espaço excessivo e provocava rolagem horizontal. Na loja pública, a prévia exibia o texto “Reproduzir no YouTube”, quando a experiência desejada era um botão de play mais limpo.

### Soluções
- Reorganizado o cabeçalho do bloco administrativo com layout flexível e quebra responsiva.
- Removida a largura mínima fixa de 260px do campo de URL.
- Em telas estreitas, o campo ocupa uma linha e os botões se distribuem na linha seguinte.
- O container passou a usar `min-width: 0` e `overflow: hidden` para impedir vazamento horizontal.
- A prévia pública agora exibe somente um botão visual de play sobre a thumbnail.
- O texto foi removido visualmente, mas o `aria-label` permanece para acessibilidade.
- Removido o ícone Bootstrap `bi-youtube` que deixou de ser utilizado pela loja.

### Validações
- `pytest -q tests/test_pagespeed_regressions.py` — **24 testes aprovados**.
- `node --check app/static/js/produtos_form.js` — aprovado.
- Templates Jinja alterados — compilados com sucesso.
- `git diff --check` — aprovado.

## 05/10/2026 — Salvamento do produto permanece na edição
### Comportamento anterior
Ao salvar um produto, o sistema sempre redirecionava para a lista principal de `/produtos`, obrigando a reabrir o cadastro para continuar trabalhando em outras abas.

### Comportamento implantado
- O botão principal agora é **Salvar e permanecer**.
- Após salvar, o sistema retorna para a página de edição do mesmo produto.
- Um toast informa **Produto salvo com sucesso**.
- A aba ativa antes do envio é preservada, inclusive após editar preços, dados técnicos ou conteúdo de e-commerce.
- Foi adicionado o botão secundário **Salvar e voltar para a lista**, mantendo o fluxo antigo como opção explícita.
- Para novos produtos, o redirecionamento após o primeiro salvamento passa a usar automaticamente a URL de edição do produto recém-criado.
- Em caso de erro de validação, o formulário continua sendo exibido na própria página.

### Validações
- `pytest -q tests/test_produtos.py` — **3 testes aprovados**.
- `node --check app/static/js/produtos_form.js` — aprovado.
- Templates Jinja do formulário — compilados com sucesso.
- `git diff --check` — aprovado.


## 06/10/2026 — Conferência física e exportação do inventário de munições

### Solicitação e escopo
Foi solicitada uma planilha para envio ao Exército contendo os dados da loja e o inventário atual de munições por código, descrição, lote, identificação da embalagem, quantidade da embalagem e quantidade total, com data da conferência. O fluxo precisava aceitar leitor de código de barras e câmera do celular, considerando embalagens de 10, 30 e 50 unidades, além de permitir PDF e Excel.

### Implementação
- Criadas as tabelas `estoque_conferencias_municao` e `estoque_conferencia_municao_itens`, com migração Alembic `20261006_inventario_municoes.py`.
- Adicionado o menu **Estoque → Conferência de munições**, com abertura de conferência por data e observação.
- A identificação da embalagem pode ser informada por leitor USB ou pela câmera do celular usando `html5-qrcode`. Quando o código já existe no estoque disponível, produto, lote e quantidade são preenchidos a partir do registro; quando não existe, a tela permite selecionar a munição e informar lote e quantidade.
- Cada embalagem é registrada apenas uma vez por conferência, mantendo snapshot dos dados necessários para auditoria e exportação. A conferência pode ser finalizada e passa a ser somente para consulta.
- Criadas exportações `.xlsx` e `.pdf`, ambas com CNPJ, nome, endereço, CR, data da conferência e as colunas do inventário. Os dados da loja são capturados no momento da abertura a partir das configurações institucionais `loja_*`.

### Validações
- `python3 -m py_compile` dos modelos, rotas e migração — aprovado.
- `git diff --check` — aprovado.
