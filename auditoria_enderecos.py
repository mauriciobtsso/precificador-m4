# auditoria_enderecos.py
from sqlalchemy import text
from app import create_app, db

app = create_app()

with app.app_context():
    print("=== AUDITORIA ENDEREÇOS ===")

    # Total
    total = db.session.execute(text("SELECT COUNT(*) FROM clientes_enderecos")).scalar()
    print(f"Total de registros: {total}")

    # Faltando logradouro
    faltando = db.session.execute(text("""
        SELECT COUNT(*)
        FROM clientes_enderecos
        WHERE logradouro IS NULL OR btrim(logradouro) = ''
    """)).scalar()
    print(f"Sem logradouro: {faltando}")

    # Preenchidos
    preenchidos = db.session.execute(text("""
        SELECT COUNT(*)
        FROM clientes_enderecos
        WHERE logradouro IS NOT NULL AND btrim(logradouro) <> ''
    """)).scalar()
    print(f"Com logradouro: {preenchidos}")

    # Ignorados
    ignorados = db.session.execute(text("""
        SELECT COUNT(*)
        FROM clientes_enderecos
        WHERE ignorado = TRUE
    """)).scalar()
    print(f"Ignorados: {ignorados}")

    print("\n--- Amostra de últimos preenchidos ---")
    rows = db.session.execute(text("""
        SELECT id, cliente_id, cep, logradouro, bairro, cidade, estado
        FROM clientes_enderecos
        WHERE logradouro IS NOT NULL AND btrim(logradouro) <> ''
        ORDER BY updated_at DESC
        LIMIT 10
    """)).fetchall()
    for r in rows:
        print(r)

    print("\n--- Amostra de ignorados ---")
    rows = db.session.execute(text("""
        SELECT id, cliente_id, cep
        FROM clientes_enderecos
        WHERE ignorado = TRUE
        ORDER BY id
        LIMIT 10
    """)).fetchall()
    for r in rows:
        print(r)

    print("\n=== FIM AUDITORIA ===")
