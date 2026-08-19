# Análise inicial do PDF `TIPOSDEDOCUMENTOS.pdf`

## Páginas 1 a 5

### Página 1
Documento introdutório descrevendo os campos relevantes esperados para os principais documentos.

#### CRAF SINARM / Polícia Federal
Campos importantes identificados no texto explicativo:
- **Nº do Registro**
- **Data de Validade**
- **Nº Cad. SINARM**
- **Espécie**
- **Marca**
- **Modelo**
- **Nº da Arma**
- **Calibre**
- **Capacidade de Tiros**
- **Funcionamento**
- **Acabamento**
- **Quantidade de Canos**
- **Comprimento dos canos**
- **Tipo de Alma**
- **Qtd de Raias**
- **Sentido das Raias**
- **País**
- **Nº da NF**
- **Data da NF**

#### CRAF SIGMA / Exército Brasileiro
Campos importantes identificados no texto explicativo:
- **Validade**
- **SFPC de Vinculação (RM)**
- **Tipo**
- **Marca**
- **Calibre**
- **Nº de Série**
- **Nº SIGMA**

#### CRAF SIGMA alternativo
O texto explica um segundo formato, comum para policiais militares, bombeiros militares, marinha, aeronáutica e alguns CACs.
Campos importantes:
- **Validade do CRAF**
- **Tipo**
- **Marca**
- **Calibre**
- **Nº Série**
- **Nº Sigma**

### Página 2
Continuação da explicação textual com documentos pessoais.

#### CNH
Campos relevantes:
- **Nº Registro**
- **Órgão Emissor**: inferir como **DETRAN**
- **Estado Emissor**: extraído do campo local/cidade-UF ou do fim do documento
- **Data de emissão**
- **Validade**

#### RG modelo novo
Campos relevantes:
- **Registro Geral / CPF / Personal Number**
- **Órgão Emissor**: sigla associada à Secretaria de Segurança Pública, como **SSP**
- **Estado emissor**
- **Data de emissão**
- **Data de validade**

#### RG Polícia Militar / militar
Campos relevantes:
- **RG nº**
- **Órgão Emissor**: **PM**
- **Estado emissor**
- **Data de emissão / expedição**
- **Validade**: quando ausente, assumir regra operacional de **10 anos após a data de emissão**

#### CR (Certificado de Registro)
Campos relevantes:
- **Nº CR**
- **Validade**
- **Emissor / SFPC / RM**
- **Atividades**

### Página 3
Exemplo visual de **CRAF SINARM** frente e verso.
Observações úteis para OCR:
- Layout horizontal com blocos densos.
- Campos distribuídos em colunas.
- O verso contém **Nº do Registro**, **Data de Validade**, **Proprietário**, **CPF** e **Doc. Identificação**.
- A frente contém dados técnicos da arma.
- O OCR deve priorizar rótulos como `Espécie`, `Marca`, `Modelo`, `Nº da Arma`, `Calibre`, `Funcionamento` e `Nº Cad. SINARM`.

### Página 4
Exemplo visual de **CRAF SIGMA** em dois lados.
Observações úteis para OCR:
- Frente: campos de identificação do proprietário e validade.
- Verso: QR Code grande e bloco compacto com **Tipo**, **Marca**, **Calibre**, **Nº de Série** e **Nº SIGMA**.
- Há alto risco de o OCR se confundir com o QR Code; convém priorizar texto próximo aos rótulos tabulares.

### Página 5
Exemplo visual do **CRAF SIGMA alternativo**.
Observações úteis para OCR:
- Frente: nome, CPF, RG, órgão expedidor e validade.
- Verso: registro, tipo, marca, calibre, nº série, nº sigma e data de expedição.
- Os rótulos parecem mais curtos (`TIPO`, `MARCA`, `Nº SÉRIE`, `Nº SIGMA`) e o texto pode ficar comprimido.

## Direções iniciais para o parser
- Diferenciar explicitamente **SINARM** vs **SIGMA** por presença de palavras-chave como `SINARM`, `POLÍCIA FEDERAL`, `EXÉRCITO BRASILEIRO`, `MINISTÉRIO DA DEFESA`, `SFPC`, `RM`.
- Em CRAF SIGMA, reforçar captura de **Nº SIGMA** e **Nº de Série** mesmo quando o modelo estiver ausente.
- Em CNH, fixar regra de **órgão emissor = DETRAN**.
- Em RG militar, permitir **órgão emissor = PM** e aplicar regra de validade derivada quando ausente.
- Em documentos de arma, o parser deve separar estritamente **modelo** de **número de série/arma**, evitando concatenar rótulos como `Nº da Arma` ao campo modelo.

## Páginas 6 a 10

### Página 6 — CNH digital
A CNH apresentada segue o padrão digital do SENATRAN com frente à esquerda e QR Code grande à direita. Os campos úteis aparecem de forma relativamente estável na frente do documento: **nome**, **CPF**, **data de nascimento**, **nº registro**, **validade**, **1ª habilitação**, **local**, **data de emissão** e a marca textual **DETRAN** na base. O estado emissor pode ser inferido por `PIAUÍ` na faixa inferior e também pelo campo `LOCAL`, que aparece como `TERESINA, PI`.

Para o OCR, o QR Code não deve ter peso interpretativo. Os sinais mais confiáveis para extração são os rótulos `Nº REGISTRO`, `VALIDADE`, `EMISSÃO` e `LOCAL`. Também fica claro que, para CNH, o órgão emissor não vem como uma sigla separada no formato tradicional de RG; portanto a regra de negócio **órgão emissor = DETRAN** continua correta.

### Página 7 — RG novo / CIN digital
O documento novo aparece em composição digital com QR Code e várias áreas complementares. A frente traz com clareza **nome**, **número do documento** em destaque, **data de nascimento**, **sexo**, **nacionalidade** e **data de validade**. No verso, aparecem **filiação**, **órgão expedidor** como `SSP/PI`, **local** (`TERESINA`), **data de expedição** e linhas MRZ na base.

Para o OCR, a leitura deve priorizar o bloco visual do documento em si, e não os quadros auxiliares da página do gov.br. O número principal tende a aparecer em formato `026.502.333-54`, e o estado pode ser obtido tanto do `SSP/PI` quanto do texto `Estado do Piauí`. O parser deve reconhecer `SSP/UF` como emissor+estado e ignorar campos não necessários como título de eleitor, NIS, PIS/PASEP e CNS.

### Páginas 8 e 9 — RG militar / Polícia Militar
Essas páginas mostram frente e verso de uma cédula da Polícia Militar. Na frente, o OCR encontra com facilidade as marcas `POLÍCIA MILITAR`, `RG Nº`, nome do portador e data de inclusão. No verso, os campos mais úteis são **local e data de expedição**, **CPF**, eventualmente **CNH**, e outros identificadores internos. O emissor é claramente militar, com marcações `PMPI` e `POLÍCIA MILITAR`.

Do ponto de vista do sistema, o parser deve mapear esse tipo para **órgão emissor = PM** e **estado emissor = PI** quando encontrar `PMPI`, `POLÍCIA MILITAR` e `PI`. A **data de emissão** deve ser capturada preferencialmente do campo `LOCAL E DATA DE EXPEDIÇÃO`. Como esse modelo antigo normalmente não mostra validade explícita, a regra operacional de derivar a validade como **10 anos após a emissão** continua plenamente justificada pelos exemplos reais.

### Página 10 — CR (Certificado de Registro)
O CR mostrado possui frente com **Nº CR**, **validade**, **nome completo**, **CPF** e **SFPC de vinculação (RM)**. O verso contém QR Code grande e o bloco **ATIVIDADES AUTORIZADAS**, além de assinatura eletrônica e identificação do SFPC.

Esse documento reforça que o OCR deve extrair prioritariamente **número do CR**, **validade**, **emissor/SFPC**, e **atividade**. O QR Code novamente é ruído. Também é importante admitir variações do número, pois o texto introdutório informa que às vezes ele aparece como `000.301.158-50` e outras vezes apenas `301158`.

## Regras e heurísticas adicionais derivadas dos exemplos reais

Os documentos analisados mostram padrões suficientemente claros para melhorar o OCR e o pós-processamento. Em CRAF de arma, vale reforçar uma heurística por família documental: quando houver `SINARM` ou `POLÍCIA FEDERAL`, priorizar rótulos longos como `Nº Cad. SINARM`, `Espécie`, `Modelo`, `Nº da Arma` e `Funcionamento`; quando houver `EXÉRCITO BRASILEIRO`, `SFPC` ou `RM`, priorizar `Tipo`, `Marca`, `Calibre`, `Nº de Série`, `Nº SIGMA` e `Validade`.

Nos documentos pessoais, a melhor abordagem é reduzir ambiguidade por tipo. Em CNH, o sistema deve buscar **registro**, **data de emissão**, **validade**, **local/UF** e assumir **DETRAN** como emissor. Em RG novo, deve usar **órgão expedidor + UF** como fonte principal para emissor e estado. Em RG militar, deve aceitar textos como `PM`, `PMPI`, `POLÍCIA MILITAR` e derivar a validade quando ela não estiver presente.

Por fim, os exemplos confirmam que o parser precisa ser muito conservador no preenchimento do campo **modelo** de armas. Nos formatos SIGMA, frequentemente o modelo nem aparece; nesses casos, é melhor retornar vazio do que contaminar o campo com `Nº de Série`, `Registro`, `CPF`, `SFPC` ou outros blocos adjacentes.
