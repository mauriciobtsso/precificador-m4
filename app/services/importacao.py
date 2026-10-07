# ================================================================
# app/services/importacao.py
# Importação de clientes TD e relatórios de vendas.
# ================================================================

import re
from datetime import date, datetime

from openpyxl import load_workbook
from app.extensions import db
from app.clientes.models import Cliente, EnderecoCliente, ContatoCliente, classificar_tipo_pessoa
from app.vendas.models import Venda, ItemVenda
from app.utils.excel_helpers import _headers_lower, _row_as_dict, _get, _as_bool
from app.utils.number_helpers import to_float
from app.utils.date_helpers import parse_data


def _documento_key(value):
    """Chave de comparação tolerante a máscara; conserva texto alfanumérico."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    return digits or text.casefold()


def _texto(value):
    """Converte células Excel para texto sem transformar números ausentes em 'None'."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    return text or None


def _data_cliente(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = parse_data(value)
    return parsed.date() if isinstance(parsed, datetime) else parsed


def _atribuir_se_preenchido(obj, campo, valor, conversor=_texto):
    """Importações incrementais: células vazias não apagam dados já cadastrados."""
    convertido = conversor(valor)
    if convertido is not None and convertido != "":
        setattr(obj, campo, convertido)
        return True
    return False


# =====================================================
# IMPORTAÇÃO DE CLIENTES (exportação Tiro Digital / TD)
# =====================================================
def importar_clientes(file_storage):
    """Importa clientes atomicamente, atualizando por CPF/CNPJ e preservando vazios.

    A planilha é lida em modo read-only; clientes, endereços e contatos atuais são
    carregados em lote para evitar uma consulta por registro (N+1).
    """
    wb = load_workbook(file_storage, read_only=True, data_only=True)
    try:
        ws = wb.active
        headers = _headers_lower(ws)
        normalized = {h.strip() for h in headers if h}
        if not ("nome" in normalized or "nome razão social" in normalized):
            raise ValueError("A planilha não contém a coluna obrigatória 'Nome'.")
        if not ("documento (cpf / cnpj)" in normalized or "documento" in normalized):
            raise ValueError("A planilha não contém a coluna obrigatória de CPF/CNPJ.")

        clientes = Cliente.query.all()
        por_documento = {}
        for cliente in clientes:
            key = _documento_key(cliente.documento)
            if key:
                por_documento.setdefault(key, cliente)

        enderecos_por_cliente = {}
        for endereco in EnderecoCliente.query.all():
            enderecos_por_cliente.setdefault(endereco.cliente_id, []).append(endereco)
        contatos_por_cliente = {}
        for contato in ContatoCliente.query.all():
            contatos_por_cliente.setdefault(contato.cliente_id, []).append(contato)

        criados = atualizados = linhas_validas = 0
        colunas_cliente = (
            ("razao_social", ("razão social", "razao social")),
            ("sexo", ("sexo",)),
            ("profissao", ("profissão", "profissao")),
            ("rg", ("rg",)),
            ("rg_emissor", ("rg emissor",)),
            ("matricula", ("matricula", "matrícula")),
            ("cr", ("cr",)),
            ("cr_emissor", ("cr emissor",)),
            ("data_validade_cr", ("cr validade", "data validade cr")),
            ("nacionalidade", ("nacionalidade",)),
            ("data_nascimento", ("data de nascimento", "data nascimento")),
            ("estado_civil", ("estado civil",)),
            ("codigo_uf_nascimento", ("uf de nascimento (código)", "uf de nascimento (codigo)")),
            ("codigo_cidade_nascimento", ("cidade de nascimento (código)", "cidade de nascimento (codigo)")),
            ("codigo_estado_civil", ("estado civil (código)", "estado civil (codigo)")),
            ("inscricao_estadual", ("inscrição estadual", "inscricao estadual")),
            ("inscricao_municipal", ("inscrição municipal", "inscricao municipal")),
            ("nome_mae", ("mãe", "mae", "nome da mãe", "nome da mae")),
            ("nome_pai", ("pai", "nome do pai")),
            ("sigma", ("sigma",)),
            ("sinarm", ("sinarm",)),
        )
        flags = (
            ("cac", ("cac",)), ("filiado", ("filiado",)),
            ("policial", ("policial",)), ("bombeiro", ("bombeiro",)),
            ("militar", ("militar",)), ("iat", ("iat",)),
            ("psicologo", ("psicologo", "psicólogo")),
            ("atirador_n1", ("atirador - nível 1", "atirador - nivel 1")),
            ("atirador_n2", ("atirador - nível 2", "atirador - nivel 2")),
            ("atirador_n3", ("atirador - nível 3", "atirador - nivel 3")),
        )
        tipos_endereco = ("residencial", "endereco_2_td", "endereco_3_td")
        endereco_campos = (
            ("cep", ("cep",)), ("estado", ("estado",)), ("cidade", ("cidade",)),
            ("codigo_estado", ("estado (código)", "estado (codigo)")),
            ("codigo_cidade", ("cidade (código)", "cidade (codigo)")),
            ("bairro", ("bairro",)), ("logradouro", ("rua",)),
            ("numero", ("numero",)), ("complemento", ("complemento",)),
        )

        for row in ws.iter_rows(min_row=2, values_only=True):
            data = _row_as_dict(headers, row)
            nome = _texto(_get(data, "nome", "nome razão social", "nome razao social"))
            if not nome:
                continue
            linhas_validas += 1
            documento = _texto(_get(data, "documento (cpf / cnpj)", "documento"))
            key = _documento_key(documento)
            cliente = por_documento.get(key) if key else None
            novo = cliente is None
            if novo:
                cliente = Cliente(nome=nome, documento=documento)
                db.session.add(cliente)
                db.session.flush()
                if key:
                    por_documento[key] = cliente
                criados += 1
            else:
                atualizados += 1
                _atribuir_se_preenchido(cliente, "nome", nome)

            _atribuir_se_preenchido(cliente, "tipo_pessoa", classificar_tipo_pessoa(documento))

            if novo:
                _atribuir_se_preenchido(cliente, "nome", nome)
            for campo, aliases in colunas_cliente:
                valor = _get(data, *aliases)
                if campo in ("data_validade_cr", "data_nascimento"):
                    _atribuir_se_preenchido(cliente, campo, valor, _data_cliente)
                else:
                    _atribuir_se_preenchido(cliente, campo, valor)

            # Naturalidade disponível no TD: cidade e UF de nascimento.
            cidade_nasc = _texto(_get(data, "uf de nascimento"))
            uf_nasc = _texto(_get(data, "cidade de nascimento"))
            # Mantém uma representação legível; dados ausentes nunca apagam naturalidade.
            if cidade_nasc or uf_nasc:
                naturalidade = " / ".join(x for x in (uf_nasc, cidade_nasc) if x)
                _atribuir_se_preenchido(cliente, "naturalidade", naturalidade)

            for campo, aliases in flags:
                raw = _get(data, *aliases)
                if raw is not None and str(raw).strip() != "":
                    setattr(cliente, campo, _as_bool(raw))

            if cliente.id is None:
                db.session.flush()
            contatos = contatos_por_cliente.setdefault(cliente.id, [])
            for aliases, tipo in (
                (("telefone",), "telefone"), (("telefone 2",), "telefone 2"),
                (("telefone 3",), "telefone 3"), (("e-mail", "email"), "email"),
                (("e-mail 2", "email 2"), "email 2"),
            ):
                valor = _texto(_get(data, *aliases))
                if not valor:
                    continue
                contato = next((c for c in contatos if (c.tipo or "").casefold() == tipo), None)
                if contato:
                    contato.valor = valor
                else:
                    contato = ContatoCliente(cliente_id=cliente.id, tipo=tipo, valor=valor)
                    db.session.add(contato)
                    contatos.append(contato)

            for idx, tipo in enumerate(tipos_endereco, start=1):
                valores = {}
                prefixo_td = any(k.startswith(f"end{idx} - ") for k in data)
                if prefixo_td:
                    for campo, sufixos in endereco_campos:
                        val = _get(data, *(f"end{idx} - {sufixo}" for sufixo in sufixos))
                        if val is not None and str(val).strip() != "":
                            valores[campo] = _texto(val)
                else:
                    # Compatibilidade com planilhas legadas de endereço sem prefixo.
                    if idx == 1:
                        for campo, aliases in (("cep", ("cep",)), ("estado", ("estado",)),
                                               ("cidade", ("cidade",)), ("bairro", ("bairro",)),
                                               ("logradouro", ("endereço", "endereco")),
                                               ("numero", ("número", "numero")),
                                               ("complemento", ("complemento",))):
                            val = _get(data, *aliases)
                            if val is not None and str(val).strip() != "":
                                valores[campo] = _texto(val)
                if not valores:
                    continue
                enderecos = enderecos_por_cliente.setdefault(cliente.id, [])
                endereco = next((e for e in enderecos if e.tipo == tipo), None)
                if endereco is None and idx == 1 and enderecos:
                    endereco = enderecos[0]
                    tipo = endereco.tipo or tipo
                if endereco is None:
                    endereco = EnderecoCliente(cliente_id=cliente.id, tipo=tipo)
                    db.session.add(endereco)
                    enderecos.append(endereco)
                for campo, valor in valores.items():
                    setattr(endereco, campo, valor)

        # Um único commit garante que falhas não deixem uma importação parcial.
        db.session.commit()
        return {"criados": criados, "atualizados": atualizados, "linhas": linhas_validas}
    except Exception:
        db.session.rollback()
        raise
    finally:
        wb.close()


# =====================================================
# IMPORTAÇÃO DE VENDAS (Relatórios TDVendas)
# =====================================================
def importar_vendas(file_storage):
    wb = load_workbook(file_storage, data_only=True)
    ws = wb.active
    headers = _headers_lower(ws)

    current_venda = None
    ultima_chave_venda = None

    for row in ws.iter_rows(min_row=2, values_only=True):
        data = _row_as_dict(headers, row)

        consumidor = _get(data, "consumidor")
        documento = str(_get(data, "documento") or "").strip() or None
        abertura = parse_data(_get(data, "abertura"))
        nf_numero = str(_get(data, "nf - nº", "nf-nº", "nf nº", default="") or "")
        chave_atual = f"{consumidor}|{abertura}|{nf_numero}"

        if consumidor and (chave_atual != ultima_chave_venda):
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
                cliente_id=cliente.id, vendedor=_get(data, "vendedor"),
                caixa=_get(data, "caixa"), status=_get(data, "status"),
                status_financeiro=_get(data, "status financeiro"), data_abertura=abertura,
                data_fechamento=parse_data(_get(data, "fechamento")),
                data_quitacao=parse_data(_get(data, "quitação", "quitacao")),
                data_cancelamento=parse_data(_get(data, "cancelamento")),
                valor_total=0.0, desconto_valor=to_float(_get(data, "descontos (r$)")),
                desconto_percentual=to_float(_get(data, "descontos (%)")),
                valor_recebido=to_float(_get(data, "valor recebido")),
                valor_faltante=to_float(_get(data, "valor faltante")),
                crediario=_as_bool(_get(data, "crediário")),
                parcelas_qtd=int(to_float(_get(data, "parcelas - qtd", default=0)) or 0),
                parcelas_primeiro_vencimento=parse_data(_get(data, "parcelas - primeiro vencimento")),
                parcelas_ultimo_vencimento=parse_data(_get(data, "parcelas - ultimo vencimento")),
                nf_data=parse_data(_get(data, "nf - data")), nf_numero=nf_numero,
                nf_valor=to_float(_get(data, "nf - valor", "nf valor")),
                teve_devolucao=_as_bool(_get(data, "teve devoluções", "teve devolucoes")),
                cliente_nome=consumidor, documento_cliente=documento,
                tipo_pessoa=_get(data, "pessoa"),
            )
            db.session.add(current_venda)
            db.session.flush()
            ultima_chave_venda = chave_atual

        if current_venda and _get(data, "produto"):
            qtd = int(to_float(_get(data, "itens - qtd", "qtd", default=1)) or 1)
            valor = to_float(_get(data, "valor"))
            subtotal = valor * qtd
            db.session.add(ItemVenda(
                venda_id=current_venda.id, produto_nome=_get(data, "produto", default=""),
                categoria=_get(data, "tipo do produto", "categoria", default=""),
                quantidade=qtd, valor_unitario=valor, valor_total=subtotal,
            ))
            current_venda.valor_total = (current_venda.valor_total or 0) + subtotal

    db.session.commit()
