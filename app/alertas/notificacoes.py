# ======================
# NOTIFICAÇÕES - BACKEND (v2 Estável e Validado)
# ======================

from datetime import datetime
from flask import jsonify
from app.models import Notificacao
from app.extensions import db


# ---------------------------------------------------
# 🔹 Função: registrar_notificacao()
# ---------------------------------------------------
def registrar_notificacao(alerta, meio="sistema"):
    """
    Registra uma nova notificação no banco, evitando duplicidades no mesmo dia.
    
    Parâmetros:
        alerta (dict): deve conter tipo, nivel, mensagem, cliente_id, cliente
        meio (str): sistema, email ou whatsapp
    """

    # ⚠️ Garantia de formato
    if not isinstance(alerta, dict):
        print(f"⚠️ Alerta inválido ignorado (esperado dict, recebido {type(alerta).__name__}): {alerta}")
        return None

    if not alerta.get("mensagem"):
        print("⚠️ Alerta sem mensagem, ignorado.")
        return None

    cliente_id = alerta.get("cliente_id")
    tipo = alerta.get("tipo")
    nivel = alerta.get("nivel")
    mensagem = alerta.get("mensagem")
    hoje = datetime.utcnow().date()

    # 🔎 Verifica duplicidade: mesmo cliente, tipo e mensagem no mesmo dia
    existente = (
        Notificacao.query.filter(
            Notificacao.cliente_id == cliente_id,
            Notificacao.tipo == tipo,
            Notificacao.mensagem == mensagem,
            db.func.date(Notificacao.data_envio) == hoje
        ).first()
    )

    if existente:
        print(f"ℹ️ Notificação já registrada hoje para cliente_id={cliente_id} ({tipo}): '{mensagem}'")
        return existente.to_dict()

    nova = Notificacao(
        cliente_id=cliente_id,
        tipo=tipo,
        nivel=nivel,
        mensagem=mensagem,
        meio=meio,
        data_envio=datetime.utcnow(),
        status="enviado"
    )

    try:
        db.session.add(nova)
        db.session.commit()
        print(f"✅ Notificação registrada: cliente={cliente_id}, tipo={tipo}, msg={mensagem}")
        return nova.to_dict()
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao registrar notificação: {e}")
        return None


# ---------------------------------------------------
# 🔹 Função: listar_notificacoes()
# ---------------------------------------------------
def listar_notificacoes(filtros=None, page=1, per_page=20):
    """
    Retorna lista paginada de notificações.
    Filtros possíveis: tipo, nivel, meio, status, q (texto livre)
    """

    query = Notificacao.query.join(Notificacao.cliente, isouter=True)

    if filtros:
        if filtros.get("tipo"):
            query = query.filter(Notificacao.tipo == filtros["tipo"])
        if filtros.get("nivel"):
            query = query.filter(Notificacao.nivel == filtros["nivel"])
        if filtros.get("meio"):
            query = query.filter(Notificacao.meio == filtros["meio"])
        if filtros.get("status"):
            query = query.filter(Notificacao.status == filtros["status"])
        if filtros.get("q"):
            texto = f"%{filtros['q'].lower()}%"
            query = query.filter(
                db.func.lower(Notificacao.mensagem).like(texto)
                | db.func.lower(Notificacao.tipo).like(texto)
                | db.func.lower(Notificacao.nivel).like(texto)
                | db.func.lower(Notificacao.meio).like(texto)
            )

    query = query.order_by(Notificacao.data_envio.desc())

    paginados = query.paginate(page=page, per_page=per_page, error_out=False)
    data = [n.to_dict() for n in paginados.items]

    return {
        "page": paginados.page,
        "pages": paginados.pages,
        "total": paginados.total,
        "data": data
    }


# ---------------------------------------------------
# 🔹 Função auxiliar: enviar_notificacao()
# ---------------------------------------------------
def enviar_notificacao(alerta, meio="sistema"):
    """
    Envia e registra a notificação.
    Nesta versão, apenas registra (não envia externamente).
    Futuramente chamará envio por e-mail/WhatsApp.
    """
    if not alerta:
        print("⚠️ Nenhum alerta recebido para envio.")
        return None

    registro = registrar_notificacao(alerta, meio)
    
    # 🔜 Futuro: integração real
    # if meio == "email": email_utils.enviar_email(alerta)
    # elif meio == "whatsapp": whatsapp_utils.enviar_mensagem(alerta)
    
    return registro
