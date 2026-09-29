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
