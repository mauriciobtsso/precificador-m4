from datetime import date
from io import BytesIO

from openpyxl import Workbook

from app import db
from app.clientes.models import Cliente, ContatoCliente, EnderecoCliente
from app.services.importacao import importar_clientes


def _xlsx(headers, rows):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


def test_importacao_td_cria_atualiza_preserva_vazios_e_importa_endereco(app):
    cpf_existente = "900.000.000-01"
    cpf_novo = "900.000.000-02"
    with app.app_context():
        existente = Cliente(nome="Nome antigo", documento=cpf_existente,
                            profissao="Profissão preservada", naturalidade="Origem preservada")
        db.session.add(existente)
        db.session.flush()
        db.session.add(ContatoCliente(cliente_id=existente.id, tipo="email", valor="antigo@example.invalid"))
        db.session.add(EnderecoCliente(cliente_id=existente.id, tipo="residencial",
                                       logradouro="Rua preservada", complemento="Fundos"))
        db.session.commit()

        headers = ["Nome", "Documento (CPF / CNPJ)", "Profissão", "E-mail", "Telefone",
                   "Telefone 2", "End1 - CEP", "End1 - Estado", "End1 - Cidade",
                   "End1 - Rua", "End1 - Numero", "End1 - Complemento", "Data de Nascimento",
                   "CR Validade", "Atirador - Nível 1", "Atirador - Nível 2", "Atirador - Nível 3",
                   "UF de Nascimento (Código)", "Cidade de Nascimento (Código)",
                   "Estado Civil (Código)", "End1 - Estado (Código)", "End1 - Cidade (Código)"]
        rows = [
            ["Nome atualizado", cpf_existente, None, None, "(11) 90000-0001", "(11) 90000-0002",
             "01000-000", "SP", "SÃO PAULO", "Rua Nova", "123", None,
             "05/04/1990", "16/06/2030", "Sim", None, None, "35", "3550308", "1", "35", "3550308"],
            ["Cliente novo", cpf_novo, "Comerciante", "novo@example.invalid", "(21) 90000-0003", None,
             "20000-000", "RJ", "RIO DE JANEIRO", "Rua Nova", "45", "Apto 2",
             "10/02/1985", None, None, "Sim", None, "33", "3304557", "2", "33", "3304557"],
        ]
        resultado = importar_clientes(_xlsx(headers, rows))

        assert resultado == {"criados": 1, "atualizados": 1, "linhas": 2}
        atualizado = Cliente.query.filter_by(documento=cpf_existente).one()
        novo = Cliente.query.filter_by(documento=cpf_novo).one()
        assert atualizado.nome == "Nome atualizado"
        assert atualizado.profissao == "Profissão preservada"
        assert atualizado.naturalidade == "Origem preservada"
        assert atualizado.data_nascimento == date(1990, 4, 5)
        assert atualizado.data_validade_cr == date(2030, 6, 16)
        assert atualizado.tipo_pessoa == "Pessoa Física"
        assert atualizado.codigo_uf_nascimento == "35"
        assert atualizado.codigo_cidade_nascimento == "3550308"
        assert atualizado.codigo_estado_civil == "1"
        assert atualizado.atirador_n1 is True
        assert {c.valor for c in atualizado.contatos} >= {
            "antigo@example.invalid", "(11) 90000-0001", "(11) 90000-0002"
        }
        endereco = next(e for e in atualizado.enderecos if e.tipo == "residencial")
        assert endereco.logradouro == "Rua Nova"
        assert endereco.complemento == "Fundos"
        assert endereco.codigo_estado == "35"
        assert endereco.codigo_cidade == "3550308"
        assert novo.nome == "Cliente novo"
        assert novo.tipo_pessoa == "Pessoa Física"
        assert novo.codigo_cidade_nascimento == "3304557"
        assert novo.estado_civil is None
        assert any(e.cidade == "RIO DE JANEIRO" for e in novo.enderecos)

        # Limpeza para não interferir nos demais testes que compartilham o app.
        db.session.query(Cliente).filter(Cliente.documento.in_([cpf_existente, cpf_novo])).delete(synchronize_session=False)
        db.session.commit()


def test_importacao_td_rejeita_planilha_sem_coluna_documento(app):
    with app.app_context():
        try:
            importar_clientes(_xlsx(["Nome"], [["Sem documento"]]))
        except ValueError as exc:
            assert "CPF/CNPJ" in str(exc)
        else:
            raise AssertionError("Deveria rejeitar planilha sem identificador CPF/CNPJ")
        assert Cliente.query.filter_by(nome="Sem documento").first() is None


def test_classifica_tipo_pessoa_por_cpf_ou_cnpj(app):
    with app.app_context():
        cpf = Cliente(nome="PF teste", documento="123.456.789-01")
        cnpj = Cliente(nome="PJ teste", documento="12.345.678/0001-95")
        invalido = Cliente(nome="Documento pendente", documento="12345")
        assert cpf.tipo_pessoa == "Pessoa Física"
        assert cnpj.tipo_pessoa == "Pessoa Jurídica"
        assert invalido.tipo_pessoa is None
