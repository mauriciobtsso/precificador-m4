# scripts/migrar_contatos.py
import sys
from datetime import datetime
from sqlalchemy import text, func, inspect

from app import create_app
from app.extensions import db
from app.clientes.models import ContatoCliente  # Cliente não é obrigatório aqui

def normalize(v):
    """Normaliza valores: strip, trata NaN/None."""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return None
    return s

def add_if_needed(cliente_id: int, tipo: str, valor: str, counters: dict):
    """Cria ContatoCliente se ainda não existir (case-insensitive por tipo+valor)."""
    valor = normalize(valor)
    if not valor:
        counters["skipped_empty"] += 1
        return

    exists = (
        db.session.query(ContatoCliente)
        .filter(ContatoCliente.cliente_id == cliente_id)
        .filter(func.lower(ContatoCliente.tipo) == func.lower(tipo))
        .filter(func.trim(func.lower(ContatoCliente.valor)) == func.lower(valor))
        .first()
    )
    if exists:
        counters["skipped_dupe"] += 1
        return

    db.session.add(ContatoCliente(cliente_id=cliente_id, tipo=tipo, valor=valor))
    counters["inserted_total"] += 1
    counters[f"inserted_{tipo}"] += 1

def main():
    app = create_app()
    with app.app_context():
        insp = inspect(db.engine)
        cols = {c["name"] for c in insp.get_columns("clientes")}

        legacy_cols = [c for c in ("email", "telefone", "celular") if c in cols]
        if not legacy_cols:
            print("✅ Nenhuma coluna legada encontrada em 'clientes' (email/telefone/celular). Nada para migrar.")
            return

        print(f"📋 Colunas legadas detectadas em 'clientes': {', '.join(legacy_cols)}")
        sel_cols = ", ".join(["id"] + legacy_cols)
        rows = db.session.execute(text(f"SELECT {sel_cols} FROM clientes")).fetchall()
        total_clientes = len(rows)
        print(f"👥 Clientes a processar: {total_clientes}")

        counters = {
            "inserted_total": 0,
            "inserted_email": 0,
            "inserted_telefone": 0,
            "inserted_celular": 0,
            "skipped_dupe": 0,
            "skipped_empty": 0,
        }

        processed = 0
        for r in rows:
            m = r._mapping  # acesso por nome
            cid = m["id"]

            if "email" in legacy_cols:
                add_if_needed(cid, "email", m["email"], counters)
            if "telefone" in legacy_cols:
                add_if_needed(cid, "telefone", m["telefone"], counters)
            if "celular" in legacy_cols:
                add_if_needed(cid, "celular", m["celular"], counters)

            processed += 1
            if processed % 500 == 0:
                db.session.commit()
                print(f"  • {processed}/{total_clientes} clientes processados...")

        db.session.commit()

        print("\n✅ Migração concluída.")
        print(f"   - Contatos inseridos (total): {counters['inserted_total']}")
        print(f"     · email:   {counters['inserted_email']}")
        print(f"     · telefone:{counters['inserted_telefone']}")
        print(f"     · celular: {counters['inserted_celular']}")
        print(f"   - Ignorados por vazio/NaN: {counters['skipped_empty']}")
        print(f"   - Ignorados por duplicidade: {counters['skipped_dupe']}")

if __name__ == "__main__":
    main()
