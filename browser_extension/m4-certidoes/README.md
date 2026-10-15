# Extensão M4 Certidões

1. Abra `chrome://extensions`, ative o **Modo do desenvolvedor** e use **Carregar sem compactação** apontando para esta pasta.
2. No M4, abra o cadastro do cliente e use os botões da central **Preenchimento assistido**.
3. O payload fica no armazenamento local da extensão por até 30 minutos e é removido depois do preenchimento.
4. Revise todos os campos, resolva CAPTCHA e faça o envio exclusivamente no portal oficial.

A extensão não preenche CAPTCHA, não assina declarações e não envia formulários automaticamente. Os portais podem alterar seus campos; nesse caso, ajuste os seletores em `portal-fill.js`.
