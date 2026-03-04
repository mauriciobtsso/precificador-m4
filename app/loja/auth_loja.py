# app/loja/auth_loja.py
"""
Sistema de autenticação EXCLUSIVO do e-commerce.

Por que não usar Flask-Login aqui?
─────────────────────────────────────────────────────────────────
Flask-Login mantém UM único "current_user" por aplicação.
Se o cliente do e-commerce fizesse login pelo Flask-Login, o sistema
confundiria com o usuário administrativo — exatamente o bug relatado.

A solução: guardar o ID do cliente em uma chave de sessão própria
(LOJA_CLIENTE_ID), completamente separada da chave do Flask-Login.
O back-end administrativo nunca lê essa chave; a loja nunca usa
o current_user do Flask-Login.
─────────────────────────────────────────────────────────────────
"""

from functools import wraps
from flask import session, redirect, url_for, flash, request
from app.clientes.models import Cliente


# Chave exclusiva da sessão do e-commerce
_SESS_KEY = "loja_cliente_id"


# ──────────────────────────────────────────
# Funções de sessão
# ──────────────────────────────────────────

def logar_cliente(cliente: Cliente) -> None:
    """Persiste o ID do cliente na sessão do e-commerce."""
    session[_SESS_KEY] = cliente.id
    session.permanent = True          # respeita PERMANENT_SESSION_LIFETIME


def deslogar_cliente() -> None:
    """Remove o cliente da sessão do e-commerce."""
    session.pop(_SESS_KEY, None)


def get_cliente_logado() -> Cliente | None:
    """
    Retorna o Cliente logado na loja, ou None.
    Nunca interfere com Flask-Login / current_user do admin.
    """
    cliente_id = session.get(_SESS_KEY)
    if not cliente_id:
        return None

    cliente = Cliente.query.filter_by(id=cliente_id, ativo_loja=True).first()
    if not cliente:
        # Sessão inválida (cliente desativado, etc.) — limpa
        deslogar_cliente()
        return None

    return cliente


def cliente_logado_required(f):
    """
    Decorator para rotas que exigem cliente da loja logado.
    Redireciona para a página de login da loja (NÃO do admin).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_cliente_logado():
            flash("Faça login para acessar esta página.", "warning")
            return redirect(url_for("loja.login", next=request.path))
        return f(*args, **kwargs)
    return decorated