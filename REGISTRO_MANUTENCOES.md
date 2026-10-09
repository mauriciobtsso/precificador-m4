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

## 06/10/2026 — Melhorias no fluxo de conferência de munições

A tela de conferência foi aprimorada para uso em celular: o campo de munição agora utiliza pesquisa digitável por código ou nome, mantendo a lista filtrável em vez de exigir rolagem manual. Conferências abertas continuam persistidas e podem ser acessadas pela ação **Continuar**, permitindo fechar a tela e retomar a sessão posteriormente com todas as embalagens já salvas.

O fluxo de leitura foi alterado para não salvar imediatamente após o bip. Depois que o leitor físico ou a câmera recebem a identificação da embalagem, o foco passa automaticamente para o campo **Lote**; o lote é convertido para maiúsculas enquanto é digitado e também é normalizado no servidor. Enter no lote avança para a quantidade, e Enter na quantidade registra a embalagem.

Os relatórios PDF e Excel passaram a consolidar as embalagens por código, descrição, calibre e lote. Cada linha mostra as identificações lidas, a quantidade de embalagens e a quantidade total de munições. Assim, três embalagens de 10 unidades do código 10029935 aparecem como 3 embalagens e 30 munições, sem perder as identificações individuais para rastreabilidade.

Validações desta rodada: compilação dos módulos alterados e `git diff --check` após a implementação.


## 06/10/2026 — Modo legado para iPad mini 1 e layout compacto do inventário

O módulo completo de conferência de munições passou a detectar o iPad mini 1 e versões antigas do iOS pelo navegador. Nessa situação, o botão de câmera é ocultado e a interface informa o uso de leitor Bluetooth configurado no modo teclado (HID). O leitor envia o código para o campo de identificação e a rotina compatível com Safari antigo usa `XMLHttpRequest`, eventos tradicionais e JavaScript ES5, sem `fetch`, `async/await`, arrow functions, optional chaining ou template literals.

Em navegadores modernos, a câmera continua disponível e a biblioteca de leitura é carregada somente quando necessária. O foco após o bip permanece no lote, com avanço por Enter para quantidade e registro. A pesquisa por código ou nome continua disponível no campo de munição.

A tela de histórico e a tela operacional receberam tipografia e espaçamentos menores, tabela responsiva e contenção de overflow horizontal. O bloco global de notificações também foi convertido de `async/fetch` para `XMLHttpRequest` e o menu passou a usar laço compatível com navegadores antigos, evitando erro de parsing do Safari iOS 9.

Validações: compilação Python, verificação de ausência de sintaxe moderna no JavaScript do modo legado, `git diff --check` e suíte existente com 74 testes aprovados.


## 06/10/2026 — Correção do botão de registro após múltiplas leituras

Corrigido um erro no callback assíncrono da tela de conferência. Quando a tabela já possuía itens, a rotina tentava remover novamente a linha vazia `emptyRow`, gerava uma exceção JavaScript depois que o servidor já havia salvo o registro e deixava o botão com aparência desabilitada. A remoção agora verifica se a linha ainda existe antes de removê-la, permitindo que o novo item seja inserido imediatamente na lista sem atualizar a página.


## 06/10/2026 — Logo e quebra de linha no PDF do inventário

O cabeçalho do PDF de inventário passou a utilizar a logo institucional `app/static/img/logo_docs.png`, posicionada ao lado do título e dos dados da loja. A tabela agora renderiza as células com `Paragraph` do ReportLab, mantendo largura fixa para quantidade de embalagens e quantidade total. As identificações das embalagens são quebradas dentro da própria célula, uma por linha quando necessário, evitando que listas com mais de 4, 10 ou 20 códigos invadam as colunas seguintes. A altura da linha cresce automaticamente e o cabeçalho continua sendo repetido em novas páginas.

Validações: PDF sintético com 22 identificações na mesma linha gerado com sucesso, logo localizada, compilação Python aprovada, `git diff --check` aprovado e suíte existente com 74 testes aprovados.


## 06/10/2026 — Otimização do espaço no PDF do inventário

O PDF foi reorganizado para exibir a logo e as informações da loja no topo, com o título **INVENTÁRIO FÍSICO DE MUNIÇÕES** centralizado logo abaixo e imediatamente antes da tabela. A coluna de identificações deixou de inserir uma quebra forçada após cada embalagem; os códigos agora permanecem na mesma linha enquanto houver espaço e quebram naturalmente dentro da própria célula quando necessário. Isso reduz a altura das linhas e conserva as colunas de quantidade de embalagens e quantidade total alinhadas.


## 06/10/2026 — Lista de conferências responsiva no celular

Corrigida a visualização da lista de conferências de munições em telas pequenas. A tabela continua disponível no PC, enquanto celulares passam a usar cartões empilhados com data, status, quantidade de embalagens, quantidade de munições, observação e botão **Continuar/Consultar** em largura total. Também foram ajustados os campos de abertura da conferência para ocuparem a largura disponível no celular, evitando que a lista fique escondida ou ultrapasse a viewport.

Validações: compilação Python, `git diff --check` e suíte existente com 74 testes aprovados.


## 06/10/2026 — Detalhes e embalagens lidas responsivos no celular

Corrigida a tela de visualização e lançamento do inventário em celulares. A tabela horizontal de embalagens lidas agora é substituída por cartões verticais em telas pequenas, exibindo código, descrição, calibre, lote, identificação da embalagem, quantidade e total sem exigir rolagem lateral. Novas leituras inseridas pelo celular também são adicionadas ao conjunto de cartões sem atualizar a página. O endereço da loja deixou de ocupar o cabeçalho da lista e passou para uma linha própria no mobile, evitando sobreposição com o título **Embalagens lidas**.

Validações: template Jinja compilado diretamente, compilação Python, `git diff --check` e suíte existente com 74 testes aprovados.


## 07/10/2026 — Compatibilidade da importação de clientes TD

### Solicitação e escopo
Foi revisado o fluxo de importação em `/importacoes` para a planilha de clientes exportada do Tiro Digital (TD). A central `/importacoes` direciona o usuário autenticado para `/importar?tipo=clientes`; o processamento é realizado por `app/services/importacao.py`. A revisão e os testes foram executados no clone do repositório, sem conexão ou gravação no banco de dados da loja.

### Diagnóstico da exportação
A planilha examinada tem 985 linhas de dados e 67 colunas. Além dos campos básicos, contém campos de documentos e registros, parentes, datas, contatos secundários, três endereços e níveis de atirador. O fluxo anterior reconhecia alguns campos pelo cabeçalho, mas não mapeava corretamente os cabeçalhos `End1/End2/End3`, `CR Validade` e campos TD adicionais; também atribuía células vazias sobre dados existentes, não importava os contatos/endereço como relações e executava uma consulta por linha ao procurar o cliente.

### Alterações implementadas
- A leitura da planilha de clientes passou a usar modo `read_only` e a carregar clientes, contatos e endereços existentes em lote, com índice em memória por CPF/CNPJ sem máscara, evitando consultas individuais por linha.
- A criação e atualização continuam identificadas por CPF/CNPJ; a formatação do documento existente é preservada. Os dados preenchidos da planilha atualizam o cadastro e células vazias não apagam informações existentes.
- Foram adicionados mapeamentos para os campos TD de razão social, sexo, profissão, RG/emissor, matrícula, CR/emissor/validade, nacionalidade, nascimento, estado civil, inscrições estadual/municipal, nomes dos pais, naturalidade, SIGMA/SINARM, indicadores e níveis de atirador.
- Telefones e e-mails secundários são armazenados em `ContatoCliente`; os endereços TD são armazenados em `EnderecoCliente`, com atualização não destrutiva e suporte aos três grupos de endereço.
- A gravação é feita em uma transação única, com rollback em caso de erro. A interface informa contagens agregadas de clientes criados e atualizados.
- Foram adicionados testes automatizados com dados sintéticos para criação, atualização, preservação de células vazias, datas, flags, contatos, endereço e rejeição de planilha sem CPF/CNPJ.

### Validações
- `python3 -m pip install -r requirements.txt` — executado porque SQLAlchemy e pytest não estavam disponíveis no ambiente. A instalação concluiu; o resolvedor reportou incompatibilidades de versão com alguns pacotes globais preexistentes do sandbox (boto3/botocore/urllib3, idna, cryptography e lxml), sem impedir os testes do projeto.
- `pytest -q tests/test_importacao_clientes_td.py` — **2 testes aprovados**.
- Prova de importação da planilha anexada em aplicação Flask com banco SQLite em memória: **985 linhas processadas, 985 clientes criados, 1.018 endereços e 1.857 contatos**. Nenhum banco externo foi acessado; os totais são agregados e nenhum dado pessoal foi registrado aqui.
- `python3 -m py_compile app/services/importacao.py` e `git diff --check` — aprovados.

### Limitação identificada
O modelo `Cliente` não possui coluna persistida para classificar Pessoa Física/Jurídica. O documento é aceito como CPF/CNPJ, mas a categoria de pessoa não pode ser armazenada pelo importador sem alteração de esquema e migração de banco. Essa alteração não foi presumida nem aplicada; exige decisão/modelagem e migração separadas antes de afirmar que a categoria fica persistida.

Também não há campos correspondentes no modelo para os códigos numéricos auxiliares de UF/cidade de nascimento, estado civil e UF/cidade dos endereços. A importação usa os nomes legíveis dessas localidades; os códigos auxiliares não são persistidos. Portanto, o arquivo é reconhecido e seus dados cadastrais mapeáveis são importados, mas não se deve dizer que os 67 valores de coluna são reproduzidos integralmente no banco atual.

### Segurança e implantação
O endpoint segue protegido por `login_required`. As alterações foram feitas somente no clone local da branch `main`; **não houve importação na loja em produção, commit, push ou migração do banco**. Antes da carga real, recomenda-se backup do banco e execução por operador autorizado no ambiente da loja.


## 07/10/2026 — Diagnóstico do HTTP 500 em `/importacoes`

### Diagnóstico somente leitura
Com autorização do usuário, foi consultado o PostgreSQL em transação somente leitura, com limite de conexão e de execução. O banco informa `alembic_version = 20261006_inventario_municoes`, que era o head do repositório antes desta correção. As tabelas `clientes`, `clientes_contatos`, `clientes_enderecos` e `importacoes_log` existem. `importacoes_log` está vazia no momento da consulta e **não contém a coluna `tipo`**, embora `ImportacaoLog` declare esse campo e a rota `/importacoes/` faça uma consulta ORM que seleciona todas as colunas do modelo. Isso causa erro de coluna inexistente no PostgreSQL e explica o HTTP 500.

A migração antiga `447f399d6bc1_adicionar_coluna_tipo_em_importacoes_log.py`, cujo título promete adicionar `tipo`, não chama `op.add_column`; ela cria índices de vendas. A migração seguinte também não adiciona o campo. A rota local, com o esquema completo gerado pelo modelo em SQLite, responde HTTP 200.

### Correção preparada (não aplicada)
- Criada a migração aditiva `20261007_importacoes_tipo`, filha do head `20261006_inventario_municoes`, adicionando `importacoes_log.tipo VARCHAR(50) NOT NULL DEFAULT 'produtos'`.
- O default atende registros/insertes anteriores sem fornecer `tipo`; como a tabela estava vazia na inspeção, não há linhas existentes a reclassificar.
- O modelo `ImportacaoLog` foi alinhado ao default server-side e foi adicionado teste de regressão para abrir a central de importações.
- Validações: `pytest -q` — **77 testes aprovados**; compilação Python, validação de grafo Alembic e `git diff --check` aprovados.

**No momento deste diagnóstico, a migração ainda não havia sido aplicada**: a autorização inicial era somente para verificar o banco, então a alteração de esquema aguardava confirmação explícita. A aplicação aprovada posteriormente está registrada abaixo. Até a confirmação, nenhum registro ou esquema foi alterado.


### Aplicação autorizada — 07/10/2026
Após confirmação explícita do usuário, a migração `20261007_importacoes_tipo` foi aplicada ao PostgreSQL. A pré-condição foi revalidada imediatamente antes da execução: revisão `20261006_inventario_municoes`, coluna ausente e zero linhas em `importacoes_log`. A pós-validação confirmou revisão `20261007_importacoes_tipo`, coluna `tipo` presente e zero linhas preservadas/alteradas na tabela de log. A aplicação Flask conectada ao mesmo banco executou `GET /importacoes/` e recebeu **HTTP 200**. A migração foi aplicada via Alembic com limite de espera para lock e timeout de instrução; nenhum outro upgrade foi solicitado e nenhuma tabela de clientes foi alterada.


## 07/10/2026 — Teste prático do upload TD pelo fluxo HTTP

Foi realizado teste de ponta a ponta pelo `POST /importar` com `tipo=clientes` e o arquivo TD anexado, em aplicação Flask de teste usando exclusivamente SQLite em memória (sem conexão ou escrita no PostgreSQL de produção). O POST foi seguido pelo GET da página de retorno.

- Primeira passagem: POST redirecionou normalmente, página final HTTP 200; mensagem agregada **985 criados / 0 atualizados**. Banco temporário ao final: 985 clientes, 1.018 endereços, 1.857 contatos.
- Segunda passagem do mesmo arquivo: POST e página final HTTP 200; **0 criados / 985 atualizados**. As contagens permaneceram idênticas, sem duplicar clientes, endereços ou contatos.
- Resultado: fluxo de upload → validação → importação → commit → retorno da interface aprovado para criação e reimportação. Nenhuma linha da planilha foi aplicada à base de produção nesta prova.


## 07/10/2026 — Importação definitiva de clientes TD em produção

Após solicitação explícita, foi executada uma pré-verificação somente leitura contra a base de produção. A planilha tinha 985 documentos únicos, sem linhas sem nome/documento e sem duplicatas; 902 documentos correspondiam a clientes existentes e 83 eram novos. A transação foi revalidada imediatamente antes da execução e bloqueou temporariamente os registros de clientes, contatos e endereços existentes para evitar sobrescrita concorrente durante a carga.

A importação foi concluída pelo serviço `importar_clientes`, que faz um commit único: **83 clientes criados, 902 atualizados, 985 linhas processadas**. As contagens de tabelas antes/depois foram: clientes 906 → 989; endereços 1.204 → 1.331; contatos 2.252 → 2.413. Na reconciliação posterior, os 985 documentos da planilha estavam presentes e não havia documento ausente nem duplicidade por chave normalizada. Nenhum valor pessoal foi impresso nos relatórios da operação.

Foi também criado e conferido um único registro agregado em `importacoes_log` (`tipo=clientes`, 83 novos, 902 atualizados, total 985), visível no histórico da central. Nenhuma migração adicional foi executada nesta carga.


## 07/10/2026 — Migração aditiva de tipo de pessoa e códigos de localidade

Após pedido explícito, foi aplicada via Alembic a revisão `20261007_pf_pj_localidade`, sucessora de `20261007_importacoes_tipo`. Em `clientes`, foram adicionadas as colunas anuláveis `tipo_pessoa`, `codigo_uf_nascimento`, `codigo_cidade_nascimento` e `codigo_estado_civil`. Em `clientes_enderecos`, foram adicionadas `codigo_estado` e `codigo_cidade`. Os códigos usam texto (`VARCHAR(20)`) para preservar zeros à esquerda; a migração não inclui defaults, restrições novas ou backfill.

A validação pós-migração confirmou a revisão Alembic, a presença dos seis campos, as contagens inalteradas (989 clientes, 1.331 endereços, 2.413 contatos) e `GET /importacoes/` com HTTP 200. Antes da aplicação, o código do modelo/importador foi alinhado para inferir Pessoa Física/Jurídica pela quantidade de dígitos do documento e ler os códigos TD sem apagar valores quando a célula está vazia. A suíte local passou: **78 testes**.

**Importante:** esta execução alterou somente o esquema. Os campos recém-adicionados dos registros existentes permanecem nulos; não foram preenchidos códigos nem reimportados dados. O código atualizado está no workspace do repositório e ainda precisa ser publicado/deployado para a aplicação produtiva começar a preencher os novos campos automaticamente.


## 07/10/2026 — Publicação e deploy da atualização TD

- O código de classificação automática PF/PJ e mapeamento dos códigos auxiliares TD foi publicado na branch `main` no commit `d1d3f9c` ([commit](https://github.com/mauriciobtsso/precificador-m4/commit/d1d3f9c9e3ec75c547f61ff338aaec9da2129ada)).
- O serviço `Loja-M4` no Render concluiu o deploy manual desse mesmo commit com estado **Deploy succeeded | Live**. O build foi concluído com sucesso; o processo iniciou o Gunicorn e o Render reconheceu a porta de serviço.
- Após o deploy, as sondagens HTTP públicas para `/` e `/importacoes/` (seguindo redirecionamentos) terminaram em **HTTP 200**.
- A suíte local foi repetida antes da publicação: **78 testes aprovados**; permaneceu apenas o aviso já conhecido do Flask-Limiter sobre armazenamento de limites em memória durante testes.
- Nenhuma reimportação de clientes nem alteração adicional de esquema foi executada durante este deploy. A migração `20261007_pf_pj_localidade`, descrita acima, já havia sido aplicada antes da publicação do código.


## 07/10/2026 — Responsividade da lista `/clientes`

A listagem desktop agora usa tabela de largura fixa com colunas proporcionais (28% nome, 18% documento, 16% telefone, 26% e-mail e 12% ações), permitindo quebra de nomes, telefones e e-mails longos sem ampliar a página. Em telas menores, foram mantidos os cartões mobile, com controles de ação acessíveis; busca e paginação também podem se acomodar em larguras reduzidas.

A contenção de largura e a quebra do cabeçalho flex foram escopadas à rota `clientes.index`. Foi identificada e contornada, somente nessa listagem, uma regra global antiga que ocultava todas as tabelas até 768 px: os cartões são mostrados abaixo de 768 px e a tabela volta a aparecer a partir desse breakpoint. Nenhuma outra página foi alterada visualmente por essa exceção.

Validação: `pytest -q` — **79 testes aprovados**; `py_compile` nos módulos/teste alterados e `git diff --check` — aprovados. Um ensaio com Chromium, aplicação de teste e dados sintéticos isolados em SQLite mediu `scrollWidth` do documento igual à largura do viewport em **320, 360, 390, 767, 768, 1024 e 1440 px**; confirmou também cartões abaixo de 768 px e tabela a partir de 768 px. Não houve acesso ou alteração ao banco de produção.

**Deploy em produção concluído:** as alterações foram publicadas na branch `main` no commit `64822c7` ([commit](https://github.com/mauriciobtsso/precificador-m4/commit/64822c7a9d1040838a79900cf37d047ce309891b)). O Render iniciou o Auto-Deploy após o push e confirmou o serviço `Loja-M4` como **Live** nesse commit, em 2m28s. Uma sondagem HTTP sem corpo em `https://loja.m4tatica.com.br/clientes/` respondeu **HTTP 200**. Nenhuma migração, importação ou alteração de dados de produção foi executada.

**Diretriz permanente solicitada pelo usuário:** após cada alteração de aplicação neste projeto, executar os testes, publicar na `main`, aguardar e confirmar o deploy de produção como **Live** e verificar por HTTP a rota impactada. Se surgir falha ou bloqueio, informar e pausar sem declarar a implantação concluída.


## 07/10/2026 — Conferência interna de dados de NF-e a partir de XML

### Solicitação e análise
Foi avaliada a solicitação de importar um XML de NF-e, permitir revisar valores e gerar um PDF semelhante à DANFE de referência. Os arquivos recebidos correspondem a uma NF-e autorizada e assinada digitalmente. Alterar valores/chave e reproduzir o layout da DANFE poderia apresentar dados modificados como se fossem a nota oficial. Por isso, o escopo implementado é uma **conferência interna**, e não a alteração do documento fiscal.

### Alterações implementadas
- Adicionada a rota autenticada `/admin/nfe/conferencia`, acessível no menu **Compras → Conferência XML (rascunho)**.
- Criado parser restrito para XML de NF-e, com limite de 2 MB, rejeição de `DOCTYPE`/entidades e máximo de 100 itens. Os bytes do XML são processados em memória e não são persistidos por esta funcionalidade.
- A tela preenche emitente, destinatário, número/série, chave de referência, totais, pagamento e itens. O usuário pode registrar valores e forma de pagamento **sugeridos** para comparação; a chave sugerida é apenas anotação interna e não é validada, assinada ou convertida em código de barras.
- O botão gera somente um relatório interno em PDF, de layout genérico, com marca d’água em todas as páginas **“RASCUNHO — SEM VALOR FISCAL”** e avisos **“NÃO É DANFE”** e **“NÃO É NF-e”**. Não inclui o logo/layout de DANFE, não altera XML, assinatura, protocolo ou autorização, e não cria barcode/QR Code fiscal.
- As respostas que exibem os dados do XML e o PDF usam `Cache-Control: no-store`. Nenhuma migração ou alteração de banco de dados foi necessária.
- Os testes usam exclusivamente dados sintéticos; nenhum conteúdo pessoal/comercial dos arquivos anexados foi copiado para o código ou fixtures.

### Validações
- `pytest -q tests/test_nfe_conferencia.py` — **4 testes aprovados**, incluindo limite e rejeição de XML com DTD/entidade, extração dos campos, fluxo de upload, PDF e validação de chave sugerida.
- `pytest -q` — **83 testes aprovados**; permaneceu somente o aviso já conhecido do Flask-Limiter sobre armazenamento em memória nos testes.
- `py_compile` nos módulos/testes alterados e `git diff --check` — aprovados.

### Limite fiscal e orientação de uso
O relatório é apenas material de conferência e não deve substituir, acompanhar ou ser apresentado como DANFE/NF-e. Para corrigir uma NF-e autorizada, a empresa deve verificar com o responsável fiscal o procedimento oficial cabível no emissor/SEFAZ. O fluxo mantém o XML original intocado.

### Publicação
A alteração foi preparada no clone local da branch `main`. A publicação e a verificação de deploy/rota serão registradas após a etapa operacional, seguindo a diretriz permanente do projeto.


### Resultado da publicação — 07/10/2026

- Código publicado na branch `main` no commit `ed58ed3` ([commit no GitHub](https://github.com/mauriciobtsso/precificador-m4/commit/ed58ed3)).
- Durante a compilação/deploy, a rota respondeu inicialmente HTTP 404; após a conclusão do deploy, a verificação pública final em `https://loja.m4tatica.com.br/admin/nfe/conferencia` respondeu **HTTP 302** para `/sistema-interno/login?next=%2Fadmin%2Fnfe%2Fconferencia`. O redirecionamento confirma que a rota está registrada e protegida por autenticação; nenhum acesso autenticado nem dado de produção foi submetido durante a sondagem.


## 08/10/2026 — Pré-validação do relatório de vendas de carrinho

### Solicitação e diagnóstico
Foi analisado o arquivo `08-10-26-Vendasdecarrinho-08_10_2026,09_45_58.csv` para verificar compatibilidade com **Importações → Vendas**, sem enviar registros ao banco de dados. O arquivo está em CSV UTF-8 e contém 45 cabeçalhos. A rota `/importar` aceita vendas somente em arquivo `.xlsx`; para vendas, chama `importar_vendas`, que usa `openpyxl` e espera o layout de relatório Excel já suportado, com campos como `Abertura`, `Fechamento`, `NF - nº`, `Produto`, `Valor` e `Itens - Qtd`. O CSV apresenta outro layout, com campos como `Data da Venda`, `Arma`, `Valor Total`, `Valor Final` e dados de aquisição, autorização, retirada e contrato.

A estrutura também não pôde ser reconstruída com segurança por leitores CSV comuns: a maior parte das linhas aparece como um único campo entre aspas e uma tentativa exploratória de desembrulhar encontrou linhas com 32 ou 45 campos, em vez de uma estrutura uniforme de 45 colunas. Portanto, não foi possível confirmar limites de registros nem mapear todos os valores sem risco de deslocar campos.

### Decisão de segurança e dados
**Nenhuma importação foi executada:** não houve conexão de leitura/escrita com o banco de produção, `importar_vendas` não foi chamado e nenhum registro de venda ou de histórico de importação foi criado. Nenhum nome, documento, número de série ou outro dado por linha foi copiado para este registro.

O importador atual não representa de forma estruturada todos os campos operacionais deste relatório (por exemplo, dados de arma, autorizações, guias e contrato). Não se deve convertê-lo automaticamente para o formato antigo sem definir como esses campos devem ser preservados e qual regra identifica uma venda para evitar duplicatas.

### Próxima etapa pendente
Aguardando o usuário escolher entre (1) enviar o relatório `.xlsx` no layout de vendas já aceito pela aplicação; ou (2) confirmar o escopo para criar um importador dedicado para este CSV, incluindo as regras de agrupamento/identificação das vendas e o tratamento dos campos extras. Até essa definição, o arquivo permanece apenas pré-validado e não importado.


## 08/10/2026 — Diretriz de linguagem para respostas de IA

A pedido do usuário, as respostas de inteligência artificial neste projeto devem seguir a técnica **ASD-STE100**. Em português, usar os princípios aplicáveis: frases curtas, palavras simples, voz ativa e termos consistentes. Não afirmar conformidade formal com regras de inglês técnico quando a resposta estiver em português.


## 08/10/2026 — Pré-validação de VENDAS.xlsx

### Estrutura e compatibilidade
O arquivo contém duas abas. **GERAL** tem 32 colunas e 476 linhas de dados; seus cabeçalhos correspondem ao importador de vendas atual. O perfil encontrou 215 linhas de resumo de venda e 261 linhas de item. Os 215 identificadores de agrupamento usados pela rotina atual são distintos. A soma de `Valor Total` das vendas é **R$ 92.831,53**, igual à soma dos itens que a rotina reconstruiria. Dez vendas sem itens são canceladas ou abertas (7 canceladas e 3 abertas); seus totais de origem não diferem do total calculado pelos itens.

A aba **ARMAS** tem 36 linhas de dados e 45 colunas. Ela não segue o esquema de itens aceito por `importar_vendas`. A rotina usa a aba ativa da pasta de trabalho, e a aba ativa deste arquivo é **ARMAS**. Portanto, enviar o arquivo original sem preparar a seleção da aba não é seguro; a rotina não escolheria `GERAL` automaticamente. Os dados específicos de ARMAS não foram incluídos na simulação de importação de `GERAL`.

### Valores que exigem tratamento
Em 119 das 215 vendas, `Descontos (%)` contém o símbolo `%`. O conversor atual `to_float` não aceita esse símbolo e gravaria **0** nesses percentuais. Os valores monetários de desconto em reais são lidos separadamente. Antes da carga, o percentual deve ser normalizado ou o conversor deve ser corrigido e testado.

### Limites da pré-validação
A simulação local da lógica atual, limitada à aba `GERAL`, estimou 215 vendas e 261 itens, sem duplicatas internas e sem diferença entre os totais por item e os totais de origem. A rotina de vendas não oferece proteção contra reimportação e não grava `ImportacaoLog`; uma segunda carga poderia duplicar vendas.

Ainda não foi possível consultar vendas existentes em produção: a central `/importacoes/` redirecionou para a tela de login e não há credencial de banco configurada neste ambiente. **Nenhuma consulta autenticada, importação ou gravação em produção foi feita.** Nenhum dado individual do arquivo foi copiado para este registro.

Antes da execução, é necessário confirmar que o escopo será a aba `GERAL` e verificar, com acesso autenticado, se há vendas duplicadas em produção. A aba `ARMAS` permanece fora do escopo aceito pelo importador atual.


## 08/10/2026 — Conferência de vendas existentes em produção

### Consulta de leitura
Com a sessão autenticada do usuário, a lista de vendas mostrou **20 registros** entre 08/10/2025 e 31/10/2025, com total agregado de **R$ 9.205,15**. A consulta de 01/11/2025 a 07/10/2026 retornou **zero registros**. O histórico de importações filtrado por vendas não mostrou importações anteriores; portanto, ele não serve como prova de que a tabela de vendas está vazia. A lista geral já continha 592 vendas.

A comparação das colunas visíveis (nome normalizado, data/hora e total bruto) encontrou 20 vendas da aba `GERAL` com o mesmo cliente e horário dos 20 registros existentes. Dezenove também têm o mesmo total bruto. Uma tem total bruto diferente. A planilha contém 22 vendas no intervalo de 08/10/2025 a 31/10/2025; duas não coincidem com registros existentes por cliente e horário.

A lista de vendas não exibe o número da NF. A abertura do detalhe de uma venda retornou erro HTTP 500. Assim, não foi possível comparar o número da NF nem confirmar a chave completa de duplicidade.

### Lote candidato e limites
Como opção conservadora, excluir as 20 vendas com cliente e horário coincidentes deixaria um lote de **195 vendas**, **236 itens** e total bruto de **R$ 82.726,38**. O lote inclui 177 vendas finalizadas, 14 canceladas e 4 abertas. Ele excluiria as 19 coincidências exatas de total e também a linha ambígua com total diferente. A aba `ARMAS` (36 linhas) continuaria fora do escopo do importador atual.

Nesse lote candidato, 108 percentuais ainda contêm `%`; o arquivo de trabalho precisaria converter esses textos em números antes da importação, pois `to_float` os transforma em zero. A pasta de trabalho original tem `ARMAS` como aba ativa; qualquer arquivo de trabalho também precisa selecionar `GERAL` como aba ativa.

**Nenhum arquivo foi enviado e nenhuma venda foi gravada em produção.** O lote candidato aguarda autorização explícita do usuário. A comparação por nome/horário é conservadora, mas não substitui a conferência do número da NF, que a tela de detalhes não permitiu fazer.

## 08/10/2026 — Tentativas autorizadas de importação de vendas não concluídas

### Arquivo preparado
Após autorização explícita do usuário, foi criada uma cópia temporária apenas com a aba `GERAL`, excluindo as 20 vendas com coincidência conservadora de cliente e horário. O lote tinha 195 vendas, 236 itens e total bruto de R$ 82.726,38; incluía 177 finalizadas, 14 canceladas e 4 abertas. Os 108 descontos textuais do lote foram convertidos em números. O arquivo original permaneceu inalterado.

A validação local com as mesmas regras de data e número do importador confirmou 195 vendas, 236 itens, datas legíveis e igualdade entre os totais das vendas e a soma dos itens. Isso valida a estrutura do lote, mas não substitui a resposta do ambiente de produção.

### Resultado em produção
A primeira submissão do formulário terminou em uma página `Internal Server Error` (HTTP 500). Uma única nova tentativa com o mesmo lote aprovado não produziu uma confirmação legível no navegador; após ela, a sessão deixou de estar autenticada. Não foi feita nova tentativa depois disso.

Após renovar o login, consultas somente de leitura confirmaram que a base continuava inalterada: total geral **592 vendas** e R$ 260.893,80; intervalo 08/10/2025–31/10/2025 com **20 vendas** e R$ 9.205,15; intervalo 01/11/2025–07/10/2026 com **zero vendas**. Portanto, nenhuma das 195 vendas do lote foi gravada.

A tela de login aberta posteriormente após demora exibiu `400 Bad Request — The CSRF token has expired`. Foi aberta uma página de login nova e o usuário autenticou-se; a mensagem CSRF referia-se à página de login expirada e não foi possível confirmar que tenha sido a causa do HTTP 500 da importação.

**Estado final:** importação pendente. Não reenviar o arquivo até que a causa do erro de produção seja investigada. Não houve alteração de aplicação ou de dados de produção nesta etapa. A cópia temporária de trabalho foi removida após as verificações; o arquivo original do usuário foi preservado.

## 09/10/2026 — Correção da busca e filtro por calibre em /catalogo
### Diagnóstico
No campo principal da página, o JavaScript copiava o texto para a busca do cabeçalho e chamava o foco desse outro campo. Isso provocava o salto observado no iPad Mini. O cabeçalho não era um formulário de busca e seu tratamento de teclado cuidava apenas de Escape; por isso, Enter podia deixar o usuário apenas no fluxo de sugestões, sem abrir resultados completos. O catálogo também não tinha filtro direto por calibre.
### Alterações
- Removida a transferência de foco e sincronização entre a busca principal e a busca do cabeçalho. O foco permanece no campo que o usuário tocou.
- Busca principal e cabeçalho agora enviam um formulário GET ao catálogo. Enter envia a busca diretamente, inclusive no Safari antigo do iPad Mini, sem depender de `requestSubmit`.
- A busca completa exige todos os termos, mas permite que cada um corresponda a campos diferentes, como nome/categoria e calibre. Inclui produto, código, descrição, marca, categoria e calibre, com variações como `9mm`, `9 mm` e `9-mm`.
- Adicionado seletor com os calibres que possuem produtos visíveis. Ele pode ser combinado com o termo da busca, preserva a consulta ao filtrar e mostra resultados completos paginados.
- As sugestões rápidas do campo de cabeçalho continuam disponíveis; Enter nesse campo agora abre os resultados completos.
### Validação e limites
Foram adicionados cinco testes de regressão para envio por formulário sem troca de foco, busca de termos em campos distintos, filtro isolado por calibre, combinação de busca e calibre e API de sugestões. A suíte completa passou: **88 testes aprovados**. Também passaram a compilação Python e `git diff --check`. O teste emitiu um aviso do Flask-Limiter sobre armazenamento em memória no ambiente de teste; não houve falha.
Nenhuma alteração de esquema ou de dados de produção foi feita. A publicação e a verificação do catálogo público ficam para a etapa seguinte.

### Publicação e verificação — 09/10/2026
O commit `b7e2110` foi enviado à branch `main`. Após a publicação, uma requisição GET sem cache para `/catalogo/` respondeu **HTTP 200**. A página de resultados apresentou o formulário principal, o seletor de calibre, o estado de nenhum resultado para um termo de teste e não continha mais a transferência de foco para `headInput`. A primeira checagem por método HEAD retornou 502 transitório; a verificação final pelo GET, que é o método usado pela tela, passou. Nenhum dado de produção foi alterado.
