# Pesquisa de alternativas de LLM — 26/08/2026

## Groq

A documentação oficial informa que os limites são medidos por RPM, RPD, TPM e TPD, aplicados no nível da organização. A tabela atual do plano Free lista, entre outros, `openai/gpt-oss-120b` e `openai/gpt-oss-20b` com 30 RPM, 1.000 RPD, 8K TPM e 200K TPD. Os valores exatos devem ser conferidos no painel da organização. O plano Developer é pago e requer forma de pagamento; uso além do gratuito pode ser faturado.

Fontes: https://console.groq.com/docs/rate-limits ; https://console.groq.com/docs/billing-faqs ; https://console.groq.com/docs/models

## Google Gemini API

A documentação oficial informa que novas contas começam no Free Tier, com acesso somente a determinados modelos e aos limites gratuitos de cada modelo. As cotas são por projeto, e o RPD reinicia à meia-noite do Pacífico. O próprio Google informa que os limites podem variar e devem ser verificados no AI Studio. Para a pesquisa, a página de preços mostra tokens de entrada e saída gratuitos para alguns modelos Flash no Free Tier, mas recursos de grounding/search não são necessariamente gratuitos. Vincular faturamento move o projeto para um tier pago; a documentação atual também descreve Prepay/Postpay e possíveis cobranças/overages durante a latência do pipeline. Não recomendar vincular faturamento para o requisito de custo zero.

Fontes: https://ai.google.dev/gemini-api/docs/rate-limits ; https://ai.google.dev/gemini-api/docs/pricing ; https://ai.google.dev/gemini-api/docs/billing

## OpenRouter

A documentação oficial informa que variantes gratuitas terminadas em `:free` têm 20 RPM. Sem créditos comprados, o limite é 50 requisições por dia; após comprar pelo menos US$10 em créditos, o limite de modelos gratuitos sobe para 1.000 RPD. O roteador `openrouter/free` é gratuito, mas seleciona um modelo aleatoriamente entre os disponíveis, e a disponibilidade, latência e qualidade podem variar. A compra de créditos envolve dinheiro, portanto não é compatível com uma política estrita de custo zero se houver compra ou saldo negativo.

Fontes: https://openrouter.ai/docs/api_reference/limits ; https://openrouter.ai/docs/faq ; https://openrouter.ai/docs/guides/routing/routers/free-router

## Cerebras

A documentação oficial atual informa que não existe nível permanentemente gratuito. O Free Trial oferece US$5 em créditos por 30 dias após adicionar método de pagamento, com limites de 5 RPM, 30K TPM, 1M TPH e 1M TPD para alguns modelos. Depois do fim/expiração do trial, o acesso para até compra de créditos. Não é indicado para o requisito de operação gratuita contínua.

Fontes: https://inference-docs.cerebras.ai/support/rate-limits ; https://www.cerebras.ai/pricing

## Conclusão preliminar

Para custo estritamente zero, manter o Groq no Free Plan é a opção mais simples no projeto atual. O problema de qualidade atual é principalmente o modelo configurado (`llama-3.1-8b-instant`) e o prompt, não necessariamente o provedor. Como alternativa a testar sem vincular billing, o Gemini Free Tier é o candidato mais forte em qualidade, mas exige conferir no AI Studio os limites do projeto e aceitar que prompts/respostas do Free Tier podem ser usados para melhoria dos produtos. OpenRouter é útil como fallback com limite baixo e qualidade variável; Cerebras não atende a operação gratuita permanente.
