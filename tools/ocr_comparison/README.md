# Piloto comparativo de leitura PDF: OCR atual do M4 × pdf_oxide

Este roteiro avalia **somente a extração de texto/OCR**. O script roda o extrator local do M4 (`pdfplumber`/Tesseract, com Poppler quando precisa rasterizar) e o modo automático do `pdf_oxide`, indicando o idioma `pt` (alias do modelo Latin). Ele não chama Groq, OCR.Space ou outro serviço externo, não grava no PostgreSQL nem altera os PDFs. O texto OCR bruto não entra no relatório JSON por padrão.

## 1. Preparar uma amostra segura

Comece com 30 PDFs para verificar instalação e cobertura; se o piloto inicial funcionar, amplie para 50–100. Inclua exemplos representativos de CRAF, CR, CNH e RG. Separe PDFs com texto embutido, digitalizados como imagem, híbridos, fotos inseridas em PDF, documentos de várias páginas e os casos conhecidos de falha. Inclua documentos legíveis e difíceis, sem selecionar apenas os piores.

Use somente documentos cuja utilização para teste tenha sido autorizada. Prefira cópias anonimizadas que preservem qualidade, orientação, resolução e tipo de arquivo. Armazene a amostra fora do repositório, em disco controlado, com acesso limitado. Não coloque PDFs, texto OCR, nomes de clientes ou relatórios de teste no Git ou em tickets sem autorização.

Para avaliar se houve melhoria real, dois revisores devem preencher uma referência manual para cada arquivo, usando o próprio documento como fonte. Para cada tipo de documento, anotem os campos aplicáveis (categoria, número principal, emissor/UF, datas e, no CRAF, tipo, marca, modelo, calibre e número de série). Marquem também se o original está legível e em quais páginas aparecem os campos. Essa referência não deve ser inferida a partir de nenhum dos OCRs.

## 2. Instalar e provisionar o ambiente

Execute na raiz do clone do projeto, em um ambiente virtual isolado. O OCR atual requer os pacotes Python declarados no `requirements.txt`, além de Tesseract com os idiomas `por` e `eng` e Poppler (`pdftoppm`/`pdfinfo`), conforme o `Dockerfile` do M4.

Instale o pacote e a dependência ONNX para a comparação:

```bash
python -m pip install -r requirements.txt
python -m pip install 'pdf_oxide[ocr]==0.3.78'
```

A versão `0.3.78` é a versão que foi inspecionada ao preparar este roteiro; o projeto upstream está em evolução. Para repetir o piloto exatamente, mantenha o pin e registre a versão do pacote. O pacote exige Python 3.9 ou superior. A versão do M4 no Docker é Python 3.12.

O script baixa os modelos de idioma apenas se for solicitado, usando a rede e o mecanismo de provisionamento do próprio pacote. Execute uma única vez no ambiente que usará o cache:

```bash
python tools/ocr_comparison/compare_pdf_ocr.py \
  --input-dir /caminho/seguro/amostra-pdfs \
  --output /caminho/seguro/resultados/ocr_comparison.json \
  --prefetch-oxide-models
```

O prefetch busca os modelos para o idioma `pt` (Latin), não envia a amostra ao serviço de modelos. Se o ambiente estiver sem rede, prepare os modelos por um procedimento de espelhamento aprovado e configure `PDF_OXIDE_MODEL_DIR`. Não prossiga interpretando um resultado vazio como teste OCR bem-sucedido: confira no relatório por página os campos `ocr_used`, `kind`, `status` e `confidence`. Se `ocr_used` nunca for verdadeiro nos PDFs escaneados, a etapa de OCR do `pdf_oxide` não foi exercitada.

## 3. Rodar a comparação

Use a mesma pasta de entrada para os dois extratores. Por padrão, o script processa até três páginas por arquivo, igual ao limite atualmente configurado em `app/services/ocr_pipeline.py`:

```bash
python tools/ocr_comparison/compare_pdf_ocr.py \
  --input-dir /caminho/seguro/amostra-pdfs \
  --output /caminho/seguro/resultados/ocr_comparison.json
```

O relatório grava identificadores derivados do SHA-256 do conteúdo, sucesso/erro por motor, tempo, páginas com texto, total de caracteres e, no caso do `pdf_oxide`, classificação, confiança e indicação de OCR por página. Não grava nome original nem texto reconhecido, a menos que as opções de inclusão sejam habilitadas.

Para relacionar os identificadores aos arquivos e revisar o texto bruto, é necessário solicitar explicitamente as opções abaixo. Faça isso somente em uma pasta privada, pois os arquivos resultantes podem conter CPF, endereço, números de documentos e outras informações pessoais. Os arquivos de saída recebem permissões restritas no sistema POSIX.

```bash
python tools/ocr_comparison/compare_pdf_ocr.py \
  --input-dir /caminho/seguro/amostra-pdfs \
  --output /caminho/seguro/resultados/ocr_comparison.json \
  --include-filenames --save-text
```

A opção `--max-pages N` altera o limite para ambos os motores. Para comparar com o comportamento corrente do site, mantenha `3`; se o problema relatado ocorrer depois da terceira página, rode uma segunda rodada com limite maior e identifique-a separadamente. As rotas atuais também enviam o PDF ao armazenamento privado antes da análise, mas este script apenas lê cópias locais da pasta indicada.

## 4. Avaliar sem confundir velocidade com precisão

O JSON fornece sinais objetivos da extração, mas não declara qual saída está correta. Compare o texto de cada motor com a transcrição/referência manual, principalmente números, letras parecidas (por exemplo `0/O`, `1/I`), datas, pontuação e ordem de leitura. A confiança de OCR é útil como indicador auxiliar, não como prova de exatidão. O `avg_confidence` do extrator atual pode vir vazio quando ele usa a camada textual do PDF; isso não deve ser interpretado como confiança zero.

A planilha/manual de revisão deve registrar, por arquivo e campo: valor de referência; valor obtido com cada OCR; acerto exato; se um revisor teve de corrigir; e minutos para revisão. Resuma acurácia exata por campo e por tipo de documento, páginas sem texto, proporção de PDFs parcialmente lidos, tempo mediano e p95, falhas e necessidade de edição manual. Dê prioridade a campos de alto impacto, como número do documento e número de série. Use os mesmos revisores e critérios para as duas saídas.

Este script não executa a Groq nem os parsers de CRAF/CR/CNH/RG. Ele isola a etapa OCR para descobrir se o texto de origem é a causa. Se `pdf_oxide` produzir texto melhor, o passo seguinte é um ensaio controlado do fluxo completo, com a mesma IA/parser e uma amostra pequena, comparando campos finais contra a referência manual. Isso demanda autorização separada para processar dados com o provedor de IA; não é feito por este utilitário.

Os benchmarks do projeto pdf_oxide medem texto extraído de um corpus de PDFs e relatam uma média de 0,8 ms, mas a própria metodologia descreve esses números como comparação de bibliotecas de **extração textual**, não como benchmark de acurácia OCR em documentos brasileiros. Trate velocidade e taxa de parser como uma alegação do upstream a validar no hardware da aplicação; não use esses números como previsão da duração do OCR digitalizado. Fontes: [repositório pdf_oxide](https://github.com/yfedoseev/pdf_oxide), [guia OCR upstream](https://github.com/yfedoseev/pdf_oxide/blob/main/docs/OCR_GUIDE.md), [benchmark e metodologia](https://pdf.oxide.fyi/docs/performance) e [registro do pacote no PyPI](https://pypi.org/project/pdf-oxide/).
