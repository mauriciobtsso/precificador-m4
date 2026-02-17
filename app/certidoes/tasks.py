# app/certidoes/tasks.py

"""
Tarefas para o módulo de Certidões.

Fluxo principal:
- emitir_certidao(certidao_id):
    - Carrega a certidão
    - Atualiza status para EM_PROCESSO
    - Chama o emissor específico conforme o tipo (TJPI, STM, TSE, TRF1)
    - Recebe o PDF em memória (bytes)
    - Envia para o R2 usando app.utils.storage.upload_file
    - Atualiza arquivo_storage_key, data_emissao e status EMITIDA
"""

import io
from datetime import timedelta

from flask import current_app

from app.extensions import db
from app.utils.datetime import now_local
from app.utils.storage import upload_file
from app.certidoes.models import Certidao, CertidaoStatus, CertidaoTipo


# ------------------------------------------------------------
# LOG SIMPLES
# ------------------------------------------------------------

def _log(msg: str):
    if current_app:
        current_app.logger.info(f"[CERTIDOES] {msg}")
    else:
        print(f"[CERTIDOES] {msg}")


# ------------------------------------------------------------
# TAREFA PRINCIPAL: EMITIR UMA CERTIDÃO (SÍNCRONA OU ASSÍNCRONA)
# ------------------------------------------------------------

def emitir_certidao(certidao_id: int):
    """
    Emite uma certidão específica (por ID), gerando um PDF e
    salvando no Cloudflare R2.

    Pode ser chamada tanto em background (fila) quanto de forma síncrona.
    """
    cert = Certidao.query.get(certidao_id)
    if not cert:
        _log(f"Certidão #{certidao_id} não encontrada.")
        return

    _log(
        f"Iniciando emissão da certidão #{cert.id} "
        f"(tipo={cert.tipo.name}, cliente_id={cert.cliente_id})"
    )

    # Se estiver cancelada, não faz nada
    if cert.status == CertidaoStatus.CANCELADA:
        _log(f"Certidão #{cert.id} está CANCELADA. Ignorando emissão.")
        return

    # Atualiza para EM_PROCESSO
    cert.status = CertidaoStatus.EM_PROCESSO
    cert.observacoes = None
    cert.atualizado_em = now_local()
    db.session.add(cert)
    db.session.commit()

    try:
        # 1) Gerar o PDF conforme o tipo
        pdf_bytes = _emitir_por_tipo(cert)

        # 2) Salvar PDF no R2
        key = _salvar_pdf_no_r2(cert, pdf_bytes)

        # 3) Atualizar dados da certidão
        cert.arquivo_storage_key = key
        cert.data_emissao = now_local()
        cert.validade_ate = (now_local() + timedelta(days=30)).date()
        cert.status = CertidaoStatus.EMITIDA
        cert.atualizado_em = now_local()

        db.session.add(cert)
        db.session.commit()

        _log(f"Certidão #{cert.id} emitida com sucesso. Key: {key}")

    except Exception as e:
        # Em caso de erro, marca como ERRO e registra motivo em observacoes
        cert.status = CertidaoStatus.ERRO
        cert.observacoes = f"Erro na emissão: {e}"[:500]
        cert.atualizado_em = now_local()
        db.session.add(cert)
        db.session.commit()

        _log(f"Falha na emissão da certidão #{cert.id}: {e}")
        raise


# ------------------------------------------------------------
# EMISSORES POR TIPO
# ------------------------------------------------------------

def _emitir_por_tipo(cert: Certidao) -> bytes:
    """
    Despacha para o emissor correto conforme CertidaoTipo.
    """
    tipo = cert.tipo

    if tipo == CertidaoTipo.ESTADUAL_TJPI:
        return _emitir_estadual_tjpi(cert)
    elif tipo == CertidaoTipo.MILITAR_STM:
        return _emitir_militar_stm(cert)
    elif tipo == CertidaoTipo.ELEITORAL_TSE:
        return _emitir_eleitoral_tse(cert)
    elif tipo == CertidaoTipo.FEDERAL_TRF1:
        return _emitir_federal_trf1(cert)

    raise RuntimeError(f"Tipo de certidão não implementado: {tipo.name}")


def _emitir_estadual_tjpi(cert: Certidao) -> bytes:
    """
    Stub de emissão da certidão Estadual TJPI (Criminal + Auditoria Militar).
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 800, "CERTIDÃO CRIMINAL + AUDITORIA MILITAR")
    c.drawString(50, 780, "TRIBUNAL DE JUSTIÇA DO ESTADO DO PIAUÍ - TJPI")

    c.setFont("Helvetica", 11)
    c.drawString(50, 750, f"Cliente ID: {cert.cliente_id}")
    c.drawString(50, 735, f"Certidão ID: {cert.id}")
    c.drawString(50, 720, f"Emitida em: {now_local().strftime('%d/%m/%Y %H:%M')}")

    c.drawString(
        50,
        690,
        "Documento gerado automaticamente pelo sistema M4 (stub para testes).",
    )
    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def _emitir_militar_stm(cert: Certidao) -> bytes:
    """
    Stub de emissão da certidão negativa de crimes militares (STM).
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 800, "CERTIDÃO NEGATIVA DE CRIMES MILITARES")
    c.drawString(50, 780, "SUPERIOR TRIBUNAL MILITAR - STM")

    c.setFont("Helvetica", 11)
    c.drawString(50, 750, f"Cliente ID: {cert.cliente_id}")
    c.drawString(50, 735, f"Certidão ID: {cert.id}")
    c.drawString(50, 720, f"Emitida em: {now_local().strftime('%d/%m/%Y %H:%M')}")

    c.drawString(
        50,
        690,
        "Documento gerado automaticamente pelo sistema M4 (stub para testes).",
    )
    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def _emitir_eleitoral_tse(cert: Certidao) -> bytes:
    """
    Stub de emissão da certidão de crimes eleitorais (TSE).
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 800, "CERTIDÃO DE CRIMES ELEITORAIS")
    c.drawString(50, 780, "TRIBUNAL SUPERIOR ELEITORAL - TSE")

    c.setFont("Helvetica", 11)
    c.drawString(50, 750, f"Cliente ID: {cert.cliente_id}")
    c.drawString(50, 735, f"Certidão ID: {cert.id}")
    c.drawString(50, 720, f"Emitida em: {now_local().strftime('%d/%m/%Y %H:%M')}")

    c.drawString(
        50,
        690,
        "Documento gerado automaticamente pelo sistema M4 (stub para testes).",
    )
    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# ------------------------------------------------------------
# FEDERAL TRF1 – AQUI VOCÊ PLUGA O ROBÔ REAL
# ------------------------------------------------------------

def _emitir_federal_trf1(cert: Certidao) -> bytes:
    """
    Emissão da certidão criminal federal (TRF1).

    - Se CERTIDOES_TRF1_MODO_STUB = True no config, usa stub.
    - Caso contrário, usa a integração REAL (_emitir_federal_trf1_real).
    """
    if current_app and current_app.config.get("CERTIDOES_TRF1_MODO_STUB"):
        _log("CERTIDOES_TRF1_MODO_STUB=TRUE, usando stub TRF1.")
        return _emitir_federal_trf1_stub(cert)

    return _emitir_federal_trf1_real(cert)


def _emitir_federal_trf1_real(cert: Certidao) -> bytes:
    """
    AQUI vai a integração REAL com o TRF1.

    Substitua o corpo desta função pelo seu código que:
      - acessa o TRF1 (Selenium / requests / etc.)
      - preenche os dados do cliente
      - baixa o PDF
      - retorna os bytes

    Enquanto não implementar, vou levantar um erro explícito para não te enganar
    gerando certidão fake.
    """
    cliente = getattr(cert, "cliente", None)
    if not cliente:
        raise RuntimeError("Certidão TRF1 sem cliente associado.")

    if not getattr(cliente, "cpf", None):
        raise RuntimeError("Cliente sem CPF cadastrado para emissão TRF1.")

    # ================================
    # COLE AQUI O SEU ROBÔ TRF1 REAL:
    # pdf_bytes = seu_robo_trf1(
    #     nome=cliente.nome,
    #     cpf=cliente.cpf,
    #     data_nascimento=cliente.data_nascimento,
    #     nome_mae=cliente.nome_mae,
    # )
    # return pdf_bytes
    # ================================

    raise RuntimeError(
        "Integração TRF1 real ainda não implementada em _emitir_federal_trf1_real."
    )


def _emitir_federal_trf1_stub(cert: Certidao) -> bytes:
    """
    Stub de emissão da certidão criminal federal (TRF1),
    usado apenas quando CERTIDOES_TRF1_MODO_STUB = True.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 800, "CERTIDÃO CRIMINAL FEDERAL")
    c.drawString(50, 780, "TRIBUNAL REGIONAL FEDERAL DA 1ª REGIÃO - TRF1")

    c.setFont("Helvetica", 11)
    c.drawString(50, 750, f"Cliente ID: {cert.cliente_id}")
    c.drawString(50, 735, f"Certidão ID: {cert.id}")
    c.drawString(50, 720, f"Emitida em: {now_local().strftime('%d/%m/%Y %H:%M')}")

    c.drawString(
        50,
        690,
        "Documento gerado automaticamente pelo sistema M4 (stub para testes).",
    )
    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# ------------------------------------------------------------
# SALVAR NO R2
# ------------------------------------------------------------

def _salvar_pdf_no_r2(cert: Certidao, pdf_bytes: bytes) -> str:
    """
    Envia o PDF para o Cloudflare R2 usando o helper centralizado.

    Retorna a key (caminho) dentro do bucket, que será gravada
    em Certidao.arquivo_storage_key.
    """
    cliente_id = cert.cliente_id or 0
    key = f"certidoes/cliente_{cliente_id}/certidao_{cert.id}.pdf"

    file_obj = io.BytesIO(pdf_bytes)
    upload_file(file_obj, key)

    return key


# ------------------------------------------------------------
# TAREFA DE TESTE (AINDA UTILIZÁVEL EM MODO ASSÍNCRONO SE HOUVER FILA)
# ------------------------------------------------------------

def tarefa_teste(certidao_id: int):
    """
    Tarefa de teste para debug: dispara a emissão da certidão.
    """
    _log(f"[TESTE] Iniciando tarefa_teste para certidão #{certidao_id}")
    emitir_certidao(certidao_id)
    _log(f"[TESTE] Finalizada tarefa_teste para certidão #{certidao_id}")
