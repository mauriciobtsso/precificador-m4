

## 08/10/2026 — Tentativas autorizadas de importação de vendas não concluídas

### Arquivo preparado
Após autorização explícita do usuário, foi criada uma cópia temporária apenas com a aba `GERAL`, excluindo as 20 vendas com coincidência conservadora de cliente e horário. O lote tinha 195 vendas, 236 itens e total bruto de R$ 82.726,38; incluía 177 finalizadas, 14 canceladas e 4 abertas. Os 108 descontos textuais do lote foram convertidos em números. O arquivo original permaneceu inalterado.

A validação local com as mesmas regras de data e número do importador confirmou 195 vendas, 236 itens, datas legíveis e igualdade entre os totais das vendas e a soma dos itens. Isso valida a estrutura do lote, mas não substitui a resposta do ambiente de produção.

### Resultado em produção
A primeira submissão do formulário terminou em uma página `Internal Server Error` (HTTP 500). Uma única nova tentativa com o mesmo lote aprovado não produziu uma confirmação legível no navegador e também foi interrompida; não foi feita nova tentativa depois disso.

Após renovar o login, consultas somente de leitura confirmaram que a base continuava inalterada: total geral **592 vendas** e R$ 260.893,80; intervalo 08/10/2025–31/10/2025 com **20 vendas** e R$ 9.205,15; intervalo 01/11/2025–07/10/2026 com **zero vendas**. Portanto, nenhuma das 195 vendas do lote foi gravada.

A tela de login aberta posteriormente após demora exibiu `400 Bad Request — The CSRF token has expired`. Foi aberta uma página de login nova e o usuário autenticou-se; a mensagem CSRF referia-se à página de login expirada e não foi possível confirmar que tenha sido a causa do HTTP 500 da importação.

**Estado final:** importação pendente. Não reenviar o arquivo até que a causa do erro de produção seja investigada. Não houve alteração de aplicação ou de dados de produção nesta etapa. A cópia temporária de trabalho foi removida após as verificações; o arquivo original do usuário foi preservado.
