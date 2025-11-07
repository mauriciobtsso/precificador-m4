# ===========================================================
# HELPER: registrar_historico()
# Centraliza o registro de histórico de alterações de produto
# Usado por: autosave.py e importar.py
# ===========================================================

from datetime import datetime
from flask_login import current_user
from app import db
from app.produtos.models import ProdutoHistorico


def registrar_historico(produto, usuario=None, origem="manual", campos_alterados=None):
    """
    Cria registros de histórico para um produto com base nos campos alterados.

    Args:
        produto: Instância de Produto.
        usuario: Instância de usuário logado (ou string com nome).
        origem: 'manual', 'autosave' ou 'importação'.
        campos_alterados: dict no formato:
            {
                "campo": {"antigo": valor_antigo, "novo": valor_novo},
                ...
            }
    """

    if not produto or not campos_alterados:
        return

    # Nome do usuário (se None, tenta obter do current_user)
    if usuario is None:
        try:
            usuario_nome = getattr(current_user, "nome", None) or getattr(current_user, "username", "Sistema")
            usuario_id = getattr(current_user, "id", None)
        except Exception:
            usuario_nome = "Sistema"
            usuario_id = None
    else:
        usuario_nome = getattr(usuario, "nome", None) or str(usuario)
        usuario_id = getattr(usuario, "id", None)

    data_atual = datetime.utcnow()

    for campo, valores in campos_alterados.items():
        valor_antigo = valores.get("antigo")
        valor_novo = valores.get("novo")

        # Ignora se os valores são idênticos (prevenção extra)
        if str(valor_antigo) == str(valor_novo):
            continue

        historico = ProdutoHistorico(
            produto_id=produto.id,
            campo=campo,
            valor_antigo=str(valor_antigo) if valor_antigo is not None else None,
            valor_novo=str(valor_novo) if valor_novo is not None else None,
            usuario_id=usuario_id,
            usuario_nome=usuario_nome,
            data_modificacao=data_atual,
            origem=origem,
        )

        db.session.add(historico)

    # Sem commit aqui — o commit é feito no fluxo chamador (autosave/importar)
