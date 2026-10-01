

### Situação de publicação após o commit

O commit `33c78e2` foi enviado com sucesso para `origin/main`. Na verificação imediatamente posterior e após três novas consultas com intervalo de 10 segundos, a URL pública respondeu HTTP 200, porém ainda entregou o HTML anterior sem `produtoLightbox`, `produtoGaleriaContador` e URLs `w=1200`. Isso indica que o provedor de hospedagem ainda não havia concluído o redeploy/propagação do commit, e não uma falha nos testes ou no código versionado. A funcionalidade está pronta na branch `main` e deve aparecer no domínio assim que o serviço concluir a atualização.
