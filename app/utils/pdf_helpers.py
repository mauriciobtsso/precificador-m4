# app/utils/pdf_helpers.py
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any, Union
from flask import current_app

from app.utils.gerar_pedidos import gerar_pedido_m4
from app.models import PedidoCompra

BytesLike = Union[bytes, bytearray, memoryview]
PathLike = Union[str, os.PathLike]


def _ensure_parent_dir(destino: Path) -> None:
    """Garante que a pasta do arquivo exista."""
    destino.parent.mkdir(parents=True, exist_ok=True)


def _unique_path(base: Path) -> Path:
    """Cria um nome único caso o arquivo já exista."""
    if not base.exists():
        return base
    stem, suffix = base.stem, base.suffix or ".pdf"
    i = 1
    while True:
        candidato = base.with_name(f"{stem} ({i}){suffix}")
        if not candidato.exists():
            return candidato
        i += 1


def _extract_bytes_from_reportlab_canvas(canvas_obj: Any) -> bytes | None:
    """Tenta extrair bytes de um canvas do ReportLab."""
    buffer_or_path = getattr(canvas_obj, "_filename", None)

    if isinstance(buffer_or_path, io.BytesIO):
        try:
            canvas_obj.save()
        except Exception:
            pass
        return buffer_or_path.getvalue()

    if isinstance(buffer_or_path, (str, os.PathLike)):
        try:
            canvas_obj.save()
            source_path = Path(buffer_or_path)
            if source_path.exists():
                return source_path.read_bytes()
        except Exception:
            return None

    getpdfdata = getattr(canvas_obj, "getpdfdata", None)
    if callable(getpdfdata):
        try:
            return getpdfdata()
        except Exception:
            return None

    return None


def _to_bytes(pdf_obj: Any) -> bytes:
    """Aceita vários formatos de PDF em memória ou disco."""
    if isinstance(pdf_obj, (bytes, bytearray, memoryview)):
        return bytes(pdf_obj)

    if isinstance(pdf_obj, io.BytesIO):
        return pdf_obj.getvalue()

    getvalue = getattr(pdf_obj, "getvalue", None)
    if callable(getvalue):
        data = getvalue()
        if isinstance(data, (bytes, bytearray, memoryview)):
            return bytes(data)

    save = getattr(pdf_obj, "save", None)
    if callable(save):
        data = _extract_bytes_from_reportlab_canvas(pdf_obj)
        if isinstance(data, (bytes, bytearray, memoryview)):
            return bytes(data)

    if isinstance(pdf_obj, (str, os.PathLike)):
        path = Path(pdf_obj)
        if path.exists():
            return path.read_bytes()

    raise TypeError("salvar_pdf: tipo de objeto não suportado.")


def salvar_pdf(
    pdf_obj: Any,
    destino_absoluto: PathLike,
    *,
    overwrite: bool = True,
) -> str:
    """
    Salva um PDF em disco, sem alterar a lógica de geração pré-existente.
    """
    destino = Path(destino_absoluto)
    _ensure_parent_dir(destino)
    if not overwrite:
        destino = _unique_path(destino)

    data = _to_bytes(pdf_obj)

    tmp_path = destino.with_suffix(destino.suffix + ".tmp")
    with open(tmp_path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, destino)

    return str(destino)


def gerar_pdf_pedido(pedido: PedidoCompra) -> str:
    """
    Gera o PDF de um PedidoCompra e retorna o caminho absoluto do arquivo.
    """
    # Monta itens
    itens = [(i.codigo, i.descricao, i.quantidade, i.valor_unitario) for i in pedido.itens]

    # Diretório de saída
    filename = f"pedido_{pedido.numero}.pdf"
    folder = Path(current_app.root_path) / "static" / "pdf"
    folder.mkdir(parents=True, exist_ok=True)
    filepath = folder / filename

    # Dados do fornecedor
    fornecedor = pedido.fornecedor
    fornecedor_nome = getattr(fornecedor, "nome", "") or ""
    fornecedor_cnpj = getattr(fornecedor, "documento", "") or ""

    # Endereço principal (preferência "comercial", senão primeiro)
    fornecedor_endereco = "-"
    if hasattr(fornecedor, "enderecos"):
        enderecos_list = list(fornecedor.enderecos)
        if enderecos_list:
            end = next((e for e in enderecos_list if e.tipo == "comercial"), enderecos_list[0])
            fornecedor_endereco = f"{(end.logradouro or '')}, {(end.numero or '')} - {(end.cidade or '')}/{(end.estado or '')}"

    # CR
    fornecedor_cr = f"CR {getattr(fornecedor, 'cr', '') or ''}"

    # Contato principal (seguro mesmo com relacionamento dynamic)
    fornecedor_contato = "-"
    if hasattr(fornecedor, "contatos"):
        contatos_list = list(fornecedor.contatos)
        if contatos_list:
            tel = next((c for c in contatos_list if c.tipo in ("telefone", "celular")), None)
            email = next((c for c in contatos_list if c.tipo == "email"), None)
            fornecedor_contato = tel.valor if tel else (email.valor if email else contatos_list[0].valor)

    # Gera PDF
    pdf_obj = gerar_pedido_m4(
        itens=itens,
        cond_pagto=pedido.cond_pagto,
        perc_armas=pedido.percentual_armas,
        perc_municoes=pedido.percentual_municoes,
        perc_unico=pedido.percentual_unico,
        modo=pedido.modo_desconto,
        numero_pedido=pedido.numero,
        data_pedido=pedido.data_pedido.strftime("%d/%m/%Y") if pedido.data_pedido else None,
        fornecedor_nome=fornecedor_nome,
        fornecedor_cnpj=fornecedor_cnpj,
        fornecedor_endereco=fornecedor_endereco,
        fornecedor_cr=fornecedor_cr,
        fornecedor_contato=fornecedor_contato,
    )

    # Salva
    salvar_pdf(pdf_obj or "pedido_m4.pdf", filepath)

    return str(filepath)
