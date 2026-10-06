

## 06/10/2026 — Melhorias no fluxo de conferência de munições

A tela de conferência foi aprimorada para uso em celular: o campo de munição agora utiliza pesquisa digitável por código ou nome, mantendo a lista filtrável em vez de exigir rolagem manual. Conferências abertas continuam persistidas e podem ser acessadas pela ação **Continuar**, permitindo fechar a tela e retomar a sessão posteriormente com todas as embalagens já salvas.

O fluxo de leitura foi alterado para não salvar imediatamente após o bip. Depois que o leitor físico ou a câmera recebem a identificação da embalagem, o foco passa automaticamente para o campo **Lote**; o lote é convertido para maiúsculas enquanto é digitado e também é normalizado no servidor. Enter no lote avança para a quantidade, e Enter na quantidade registra a embalagem.

Os relatórios PDF e Excel passaram a consolidar as embalagens por código, descrição, calibre e lote. Cada linha mostra as identificações lidas, a quantidade de embalagens e a quantidade total de munições. Assim, três embalagens de 10 unidades do código 10029935 aparecem como 3 embalagens e 30 munições, sem perder as identificações individuais para rastreabilidade.

Validações desta rodada: compilação dos módulos alterados e `git diff --check` após a implementação.
