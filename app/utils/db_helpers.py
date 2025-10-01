# app/utils/db_helpers.py
from flask import abort
from app import db

def get_or_404(model, id):
    """
    Busca um objeto pelo ID usando db.session.get.
    Se não encontrar, retorna erro 404.
    """
    obj = db.session.get(model, id)
    if not obj:
        abort(404)
    return obj
