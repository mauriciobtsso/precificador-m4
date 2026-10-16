
### Publicação e correção do identificador Alembic

A primeira ativação do commit `69d8a88` foi interrompida porque o identificador da revisão Alembic excedia o limite de 32 caracteres da coluna de versão do PostgreSQL. O identificador foi encurtado para `20261016_sep_end_res` no commit `f612418`. Os logs do deploy confirmam a execução da migração de `20261016_update_declaracoes` para `20261016_sep_end_res`, seguida da inicialização do Gunicorn. O deploy `f612418` ficou **live**; a rota `/admin/documentos` continua redirecionando para o login, e `/clientes` responde com o redirecionamento canônico para `/clientes/`.
