# API de leitura do catálogo para o OpenLivery

Esta API permite que um agente consulte os produtos públicos da loja. Ela não cria pedidos e não altera produtos.

## Segurança e configuração

Todas as rotas exigem `Authorization: Bearer <token>`. Configure a variável de ambiente `OPENLIVERY_CATALOG_API_KEY` no serviço que hospeda a loja. Gere um valor aleatório forte, por exemplo, com `python -c 'import secrets; print(secrets.token_urlsafe(48))'`.

Guarde o token somente no gerenciador de segredos da hospedagem e no campo de cabeçalho da ferramenta HTTP do OpenLivery. Não o inclua no código, em arquivos `.env` enviados ao GitHub, em mensagens, logs ou neste guia. Após definir a variável na hospedagem, reinicie ou publique o serviço para que a aplicação a leia.

A API aceita somente `GET`, retorna somente produtos com `visivel_loja=True` e marca as respostas como `no-store`. O limite configurado é 120 chamadas por minuto por IP, mas o Flask-Limiter do projeto usa atualmente armazenamento em memória. Portanto, a contagem é local a cada processo/worker e não é um limite global distribuído. Não há CORS porque o uso previsto é uma chamada servidor a servidor pelo OpenLivery. A resposta omite custos, margem, lucro, preço do fornecedor e quantidade exata de estoque. A disponibilidade é resumida como `in_stock`, `out_of_stock` ou `unknown`.

## Rotas

### Buscar produtos

`GET https://loja.m4tatica.com.br/api/v1/catalogo/produtos?q=<termo>&page=1&per_page=10`

- `q`: obrigatório; 2 a 120 caracteres.
- `page`: opcional; inicia em `1`.
- `per_page`: opcional; inicia em `10`; aceita de `1` a `20`.
- A busca considera nome, nome de exibição, código, marca, categoria, calibre, tags públicas e descrição comercial. Para vários termos, cada termo deve corresponder a algum campo do produto.

Exemplo:

```bash
curl --fail-with-body \
  -H 'Authorization: Bearer SEU_TOKEN' \
  -H 'Accept: application/json' \
  'https://loja.m4tatica.com.br/api/v1/catalogo/produtos?q=lanterna&page=1&per_page=10'
```

A resposta tem a forma:

```json
{
  "products": [
    {
      "id": 123,
      "code": "COD-123",
      "name": "Nome público do produto",
      "slug": "nome-publico-do-produto",
      "category": "Acessórios",
      "brand": "Marca",
      "price_brl": "249.90",
      "promotion_active": false,
      "availability": "in_stock",
      "documentation_required": false,
      "image_url": "https://cdn.example/imagem.webp",
      "product_url": "https://loja.m4tatica.com.br/produto/nome-publico-do-produto"
    }
  ],
  "pagination": {"page": 1, "per_page": 10, "total": 1, "pages": 1}
}
```

`price_brl` é o preço atual calculado pelas regras da loja, retornado como texto decimal com duas casas. `promotion_active` informa se a regra de promoção existente está ativa no momento da consulta.

### Consultar detalhes

`GET https://loja.m4tatica.com.br/api/v1/catalogo/produtos/<slug>`

A resposta contém `product` com os campos da busca e também `description`, `specifications` e `images`. A descrição longa é convertida em texto; conteúdo de `script` e `style` é ignorado. Somente imagens com URL pública são retornadas.

Exemplo:

```bash
curl --fail-with-body \
  -H 'Authorization: Bearer SEU_TOKEN' \
  -H 'Accept: application/json' \
  'https://loja.m4tatica.com.br/api/v1/catalogo/produtos/nome-publico-do-produto'
```

## Configuração no OpenLivery

Crie duas ferramentas HTTP, ambas com método `GET` e o cabeçalho `Authorization` com valor `Bearer <token>`:

1. **buscar_produtos** — URL `https://loja.m4tatica.com.br/api/v1/catalogo/produtos`; adicione o parâmetro de consulta `q` e, se necessário, `page` e `per_page`.
2. **consultar_produto** — URL `https://loja.m4tatica.com.br/api/v1/catalogo/produtos/{slug}`; configure `slug` como parâmetro de caminho.

Uma instrução de uso para o agente pode dizer: “Use `buscar_produtos` para localizar itens. Use `consultar_produto` para obter descrição e especificações. Informe preços e disponibilidade conforme a resposta mais recente da ferramenta. Se a ferramenta falhar ou não encontrar o produto, diga que não conseguiu confirmar; não invente preço, estoque ou características.”

## Respostas de erro

- `400`: parâmetro de busca ou paginação inválido.
- `401`: cabeçalho ausente ou token incorreto.
- `404`: produto inexistente ou não visível na loja.
- `429`: limite de chamadas atingido.
- `503`: `OPENLIVERY_CATALOG_API_KEY` ainda não foi configurada na hospedagem.
