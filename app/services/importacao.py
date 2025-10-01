# app/services/importacao.py
from openpyxl import load_workbook
from app.extensions import db
from app.clientes.models import Cliente
from app.models import Venda, ItemVenda
from app.utils.excel_helpers import _headers_lower, _row_as_dict, _get, _as_bool
from app.utils.number_helpers import to_float
from app.utils.date_helpers import parse_data


def importar_clientes(file_storage):
    wb = load_workbook(file_storage, data_only=True)
    ws = wb.active
    headers = _headers_lower(ws)

    for row in ws.iter_rows(min_row=2, values_only=True):
        data = _row_as_dict(headers, row)

        nome = _get(data, "nome razão social", "nome")
        if not nome:
            continue

        doc = str(_get(data, "documento (cpf / cnpj)", "documento") or "").strip()
        if not doc:
            doc = None

        cliente = Cliente.query.filter_by(documento=doc).first() if doc else None
        if not cliente:
            cliente = Cliente(nome=nome, documento=doc)
            db.session.add(cliente)

        cliente.nome = nome
        cliente.razao_social = _get(data, "razão social", "razao social", default="")
        cliente.sexo = _get(data, "sexo", default="")
        cliente.profissao = _get(data, "profissão", "profissao", default="")
        cliente.rg = _get(data, "rg", default="")
        cliente.rg_emissor = _get(data, "rg emissor", default="")
        cliente.email = _get(data, "e-mail", "email", default="")
        cliente.telefone = _get(data, "telefone", default="")
        cliente.celular = _get(data, "celular", default="")
        cliente.endereco = _get(data, "endereço", "endereco", default="")
        cliente.numero = str(_get(data, "número", "numero", default="") or "")
        cliente.complemento = _get(data, "complemento", default="")
        cliente.bairro = _get(data, "bairro", default="")
        cliente.cidade = _get(data, "cidade", default="")
        cliente.estado = _get(data, "estado", default="")
        cliente.cep = _get(data, "cep", default="")
        cliente.cr = _get(data, "cr", default="")
        cliente.cr_emissor = _get(data, "cr emissor", default="")
        cliente.sigma = _get(data, "sigma", default="")
        cliente.sinarm = _get(data, "sinarm", default="")
        cliente.cac = _as_bool(_get(data, "cac"))
        cliente.filiado = _as_bool(_get(data, "filiado"))
        cliente.policial = _as_bool(_get(data, "policial"))
        cliente.bombeiro = _as_bool(_get(data, "bombeiro"))
        cliente.militar = _as_bool(_get(data, "militar"))
        cliente.iat = _as_bool(_get(data, "iat"))
        cliente.psicologo = _as_bool(_get(data, "psicologo"))

    db.session.commit()


def importar_vendas(file_storage):
    wb = load_workbook(file_storage, data_only=True)
    ws = wb.active
    headers = _headers_lower(ws)

    current_venda = None

    for row in ws.iter_rows(min_row=2, values_only=True):
        data = _row_as_dict(headers, row)

        consumidor = _get(data, "consumidor")
        documento = str(_get(data, "documento") or "").strip()
        if documento == "":
            documento = None

        if consumidor:
            if documento:
                cliente = Cliente.query.filter_by(documento=documento).first()
                if not cliente:
                    cliente = Cliente(nome=consumidor or "", documento=documento)
                    db.session.add(cliente)
                    db.session.flush()
            else:
                cliente = Cliente.query.filter_by(documento=None, nome="Consumidor não identificado").first()
                if not cliente:
                    cliente = Cliente(nome="Consumidor não identificado", documento=None)
                    db.session.add(cliente)
                    db.session.flush()

            current_venda = Venda(
                cliente_id=cliente.id,
                vendedor=_get(data, "vendedor"),
                status=_get(data, "status"),
                status_financeiro=_get(data, "status financeiro"),
                data_abertura=parse_data(_get(data, "abertura")),
                data_fechamento=parse_data(_get(data, "fechamento")),
                data_quitacao=parse_data(_get(data, "quitação", "quitacao")),
                valor_total=to_float(_get(data, "valor total")),
                nf_numero=str(_get(data, "nf - nº", "nf-nº", "nf nº", default="") or ""),
                nf_valor=to_float(_get(data, "nf - valor", "nf valor")),
                teve_devolucao=_as_bool(_get(data, "teve devoluções", "teve devolucoes")),
            )
            db.session.add(current_venda)
            db.session.flush()

            produto_nome = _get(data, "produto")
            if produto_nome:
                qtd = int(to_float(_get(data, "itens - qtd", "qtd", default=1)) or 1)
                valor = to_float(_get(data, "valor"))
                item = ItemVenda(
                    venda_id=current_venda.id,
                    produto_nome=produto_nome,
                    categoria=_get(data, "tipo do produto", "categoria", default=""),
                    quantidade=qtd,
                    valor_unitario=valor,
                    valor_total=valor * qtd,
                )
                db.session.add(item)

            continue

        if current_venda and _get(data, "produto"):
            qtd = int(to_float(_get(data, "itens - qtd", "qtd", default=1)) or 1)
            valor = to_float(_get(data, "valor"))
            item = ItemVenda(
                venda_id=current_venda.id,
                produto_nome=_get(data, "produto", default=""),
                categoria=_get(data, "tipo do produto", "categoria", default=""),
                quantidade=qtd,
                valor_unitario=valor,
                valor_total=valor * qtd,
            )
            db.session.add(item)

    db.session.commit()
