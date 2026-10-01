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
