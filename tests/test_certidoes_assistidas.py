from datetime import date

from app.certidoes.declaracoes import gerar_declaracao
from app.certidoes.portal_catalog import PORTAIS, cliente_payload
from app.clientes.models import Cliente, ContatoCliente, EnderecoCliente


def test_catalogo_contem_sete_portais_oficiais():
    assert set(PORTAIS) == {"stm", "mppi", "mpf", "tjpi", "tse", "cjf", "pc_pi"}
    assert all(item["url"].startswith("https://") for item in PORTAIS.values())


def test_payload_normaliza_dados_do_cliente():
    cliente = Cliente(id=42, nome="Ana Teste", documento="123.456.789-00", data_nascimento=date(1980, 1, 2), nome_mae="Maria")
    cliente.enderecos = [EnderecoCliente(tipo="residencial", cep="64000-000", logradouro="Rua A", numero="10", cidade="Teresina", estado="PI")]
    cliente.contatos = [ContatoCliente(tipo="email", valor="ana@example.com")]
    payload = cliente_payload(cliente)
    assert payload["cpf"] == "12345678900"
    assert payload["cep"] == "64000000"
    assert payload["data_nascimento"] == "1980-01-02"
    assert payload["email"] == "ana@example.com"


def test_declaracoes_geram_pdf_com_cabecalho():
    cliente = Cliente(id=7, nome="Ana Teste", documento="12345678900")
    cliente.enderecos = [EnderecoCliente(tipo="residencial", logradouro="Rua A", numero="10", cidade="Teresina", estado="PI")]
    for tipo, titulo in (("residencia", "DECLARAÇÃO DE RESIDÊNCIA"), ("nao_inquerito", "DECLARAÇÃO DE NÃO RESPONDER A INQUÉRITO POLICIAL")):
        pdf = gerar_declaracao(cliente, tipo)
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 1000
