# Extensão M4 Certidões

## Instalação ou atualização

1. Abra `chrome://extensions` e ative o **Modo do desenvolvedor**.
2. Na extensão M4 Certidões, clique em **Recarregar**. Se ainda não estiver instalada, use **Carregar sem compactação** e selecione esta pasta.
3. Depois de atualizar a extensão, recarregue também a página do portal que estava aberta.
4. No M4, abra o cadastro do cliente e use os botões da central **Preenchimento assistido**.

A versão atual é **1.0.5**. A extensão guarda o cliente selecionado no armazenamento local por até 30 minutos. Após o preenchimento, confira visualmente os campos antes de continuar.

## Uso e segurança

- A extensão não preenche CAPTCHA, não assina declarações e não envia formulários.
- O envio deve ser feito manualmente no portal oficial, após revisar todos os campos.
- Se um portal mudar seus campos, atualize os seletores em `portal-fill.js`.

## Testes locais

Execute `node --test tests/browser_extension/portal-fill.test.js` na raiz do repositório.
