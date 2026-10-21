# Análise de reutilização do DeskcommCRM sem VPS

## Conclusão

É tecnicamente possível reutilizar o [DeskcommCRM](https://github.com/melgarafael/DeskcommCRM) no ecossistema da M4 Tática, mas não como um módulo que seja simplesmente copiado para dentro do precificador. O DeskcommCRM é uma aplicação independente em Next.js/React, com Supabase, workers, scheduler e WAHA para WhatsApp. A integração mais segura é manter os dois sistemas separados e conectá-los por links, API e webhooks.

A opção sem custo mais próxima da instalação oficial é executar o DeskcommCRM em uma máquina persistente gratuita, como uma instância Always Free da Oracle Cloud, ou em um computador próprio. Isso não é uma VPS paga, mas ainda exige administrar uma máquina, Docker, backups, domínio/rede e disponibilidade. A opção totalmente serverless é possível apenas se o WhatsApp for adaptado para a Meta Cloud API e os workers do CRM forem convertidos para jobs curtos; ela não executa o WAHA como está.

## O que foi confirmado

- O precificador atual é uma aplicação Flask/Python em container Docker, com Gunicorn, Alembic, PostgreSQL e tarefas Python. Seu `Dockerfile` executa a migração antes de iniciar a aplicação.
- O DeskcommCRM usa Next.js 16, React, Supabase, Supabase Auth/Storage/Realtime, `event_log`, workers e scheduler. O README do projeto declara que o caminho principal de produção é uma instalação Docker em VPS e recomenda 4 GB de RAM.
- O fluxo de WhatsApp por QR depende do WAHA, um processo/container que precisa permanecer ativo para manter a sessão e receber webhooks. O projeto também depende de workers e de um cron para drenar automações; isso não combina com uma função serverless que inicia e termina por requisição.
- O DeskcommCRM está sob licença MIT. É permitido usar, modificar e distribuir o código, mantendo o aviso de copyright e a licença. A licença não elimina as obrigações dos serviços dependentes, como WhatsApp/Meta, provedores de IA, e-mail e eventuais imagens Docker.

## Alternativas sem VPS paga

### 1. Oracle Cloud Always Free: alternativa mais próxima do deploy oficial

Uma VM Arm Ampere A1 Always Free pode hospedar Docker, o app, os workers, o scheduler e o WAHA. A página oficial informa até 4 vCPUs OCPU e 24 GB de memória para o conjunto Arm, sujeitos à disponibilidade; o próprio DeskcommCRM documenta suporte a ARM64.

**Vantagens:** preserva a arquitetura original, permite WAHA por QR, workers contínuos e cron; custo mensal pode permanecer zero dentro da cota.

**Limitações:** a Oracle pode exigir cartão para cadastro, há risco de falta de capacidade na região, a máquina e os backups ficam sob nossa responsabilidade e uma conta Always Free não deve ser tratada como SLA. Também é necessário endurecer segurança, configurar firewall, domínio, TLS e cópias externas.

**Veredito:** melhor opção para testar o DeskcommCRM completo sem contratar uma VPS, desde que aceitemos operar uma VM gratuita.

### 2. Computador próprio ou mini-PC: custo financeiro zero

O DeskcommCRM pode rodar em Docker em um computador ligado continuamente, com o precificador permanecendo no serviço atual. Um túnel seguro ou um domínio com proxy reverso pode expor somente as rotas necessárias.

**Vantagens:** não depende de cota de cloud e mantém WAHA, workers e scheduler funcionando.

**Limitações:** queda de energia, internet residencial, IP variável, CGNAT, segurança e disponibilidade. Para produção comercial, é uma solução de teste ou de baixo risco, não uma garantia de continuidade.

**Veredito:** bom para validação interna e piloto com poucos atendentes.

### 3. Meta Cloud API + Supabase + hospedagem serverless

Podemos hospedar o frontend/rotas compatíveis em uma plataforma serverless e usar o Supabase Free para banco, autenticação, storage e realtime. Os webhooks da Meta podem entrar por uma função HTTP e as tarefas curtas podem ser acionadas por cron. Nesse desenho, o WAHA/QR é removido e a conexão passa a ser o canal oficial da Meta, com templates e regras da plataforma.

O Supabase Free informa 500 MB de banco, 1 GB de arquivos, 5 GB de egress e até dois projetos ativos, mas pausa projetos após uma semana de inatividade e não inclui backup automático. Isso é suficiente para um piloto pequeno, desde que haja exportação/backup independente.

**Vantagens:** não exige processo persistente, Docker ou VM; pode ser barato ou gratuito em pequena escala.

**Limitações:** exige adaptação real no DeskcommCRM; perde o fluxo de QR/WAHA; a Meta exige configuração e aprovação próprias; provedores de IA, e-mail e domínio continuam podendo gerar custos.

**Veredito:** melhor alternativa para uma versão enxuta e oficial do WhatsApp, não para executar o DeskcommCRM atual sem alterações.

### 4. Cloudflare Workers para webhooks e jobs curtos

Workers pode complementar a alternativa anterior. O plano gratuito informa 100.000 requisições por dia, 10 ms de CPU por requisição e 5 cron triggers por conta. Isso serve para receber webhooks, validar payloads e disparar tarefas pequenas, mas não para manter WAHA, uma conexão persistente ou um worker Node/Docker contínuo.

**Veredito:** útil como componente serverless, não como substituto direto da infraestrutura do DeskcommCRM.

### 5. Vercel Hobby para o Next.js

Embora o DeskcommCRM use Next.js, o plano Hobby da Vercel é destinado a uso pessoal e não comercial. Além disso, as funções têm duração máxima documentada de 300 segundos. Portanto, não recomendo usar o Hobby para a operação comercial da M4 Tática nem para substituir WAHA/workers persistentes. Mesmo que o frontend seja implantado ali, banco, WhatsApp e processamento contínuo continuariam separados.

### 6. Incorporar apenas as telas e conceitos ao precificador

Outra estratégia é estudar o DeskcommCRM e implementar no Flask somente o que for necessário: contatos, funil, histórico, tarefas e links para atendimento. Isso evita uma segunda aplicação em produção e pode aproveitar o PostgreSQL já usado pelo precificador.

**Vantagens:** uma única autenticação, uma única implantação e menor quantidade de serviços.

**Limitações:** é o caminho de maior desenvolvimento; não reaproveita automaticamente a arquitetura Next.js, o schema Supabase, o WAHA, os workers ou os testes do DeskcommCRM. Deve ser feito sem copiar dados, segredos ou componentes incompatíveis sem uma análise de licença e segurança.

**Veredito:** adequado se o objetivo for apenas um CRM simples integrado ao cadastro de clientes e pedidos, não se forem necessárias todas as funções de WhatsApp/IA do DeskcommCRM.

## Recomendação para a M4 Tática

1. **Não misturar os bancos nem copiar o DeskcommCRM para dentro do Flask agora.** Manter o precificador como sistema principal e preservar sua implantação atual.
2. **Fazer um piloto separado do DeskcommCRM** em Oracle Always Free ou em um computador próprio. Usar o Supabase Free externo para banco/auth/storage, se o consumo couber nos limites, e começar sem IA paga.
3. **Integrar primeiro por links e API mínima:** link do cliente no precificador para o CRM, identificador externo do cliente, webhook de criação/atualização e retorno de status. Não duplicar dados sensíveis sem necessidade.
4. **Para produção com WhatsApp**, escolher entre WAHA em uma máquina persistente gratuita e Meta Cloud API com adaptação serverless. A primeira preserva o DeskcommCRM original; a segunda reduz a infraestrutura, mas abandona o QR e exige desenvolvimento.
5. **Definir backup antes de dados reais.** O Supabase Free não fornece backup automático no plano gratuito, e a VM gratuita também pode falhar. Exportar banco, configurações e mídia para armazenamento independente e testar restauração.
6. **Não usar Vercel Hobby como base comercial.** Se a aplicação for comercial, usar o serviço já disponível para o precificador ou outro plano/host cuja licença de uso seja compatível.

## Escopo desta manutenção

Esta análise não altera o código funcional do precificador e não instala o DeskcommCRM. O próximo passo, caso aprovado, deve ser um piloto isolado com definição de quais dados serão compartilhados e qual canal de WhatsApp será utilizado.

## Referências

[1]: https://github.com/melgarafael/DeskcommCRM "DeskcommCRM — código-fonte, arquitetura e instruções de implantação"
[2]: https://raw.githubusercontent.com/melgarafael/DeskcommCRM/main/LICENSE "Licença MIT do DeskcommCRM"
[3]: https://supabase.com/pricing "Supabase — preços e limites do plano Free"
[4]: https://vercel.com/docs/plans/hobby "Vercel — plano Hobby"
[5]: https://developers.cloudflare.com/workers/platform/limits/ "Cloudflare Workers — limites da plataforma"
[6]: https://www.oracle.com/cloud/free/ "Oracle Cloud — Free Tier e serviços Always Free"
