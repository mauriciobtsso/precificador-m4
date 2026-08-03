# Implementação de Busca Fuzzy Inteligente - Precificador M4

Esta documentação detalha a implementação da busca "inteligente" em tempo real na vitrine da loja pública.

## 1. Banco de Dados (PostgreSQL)
- **Extensão:** Ativada a extensão `pg_trgm` para suporte a similaridade de trigramas.
- **Índices:** Criados índices `GIN` com `gin_trgm_ops` nas colunas `nome`, `nome_comercial` e `codigo` da tabela `produtos`.
- **Migration:** `migrations/versions/20260802_fuzzy_search_trgm.py`.

## 2. Backend (Flask)
- **Rota:** `/api/buscar` implementada no blueprint `loja_bp` (`app/loja/routes.py`).
- **Lógica:** 
    - Utiliza `func.similarity` e o operador `%` do PostgreSQL para encontrar resultados tolerantes a erros de digitação.
    - Ordena os resultados pela maior similaridade encontrada entre os campos buscados.
    - Limita o retorno aos top 10 resultados.
- **Cache:** Aplicado `@cache.cached(timeout=300, query_string=True)` para otimizar a performance e reduzir carga no banco de dados.
- **JSON:** Retorna `id`, `nome`, `slug`, `preco` e `foto` (thumbnail pequena).

## 3. Frontend (Header)
- **Template:** Modificado `app/loja/templates/loja/base.html`.
- **UI:** Adicionado dropdown dinâmico abaixo do input de busca.
- **JavaScript:** 
    - Implementado em **ES5 puro** para compatibilidade máxima (iOS 9+).
    - **Debounce:** Espera de 300ms antes de disparar a requisição para a API.
    - **AJAX:** Utiliza `XMLHttpRequest` nativo.
    - **Interatividade:** Fecha o dropdown ao clicar fora e reabre ao focar no input se houver resultados.

## Regras de Negócio Aplicadas
- A busca só é disparada a partir de 2 caracteres.
- Preços são formatados em BRL (R$) via JavaScript.
- Fallback automático para busca `ILIKE` caso a extensão `pg_trgm` não esteja disponível no ambiente.
