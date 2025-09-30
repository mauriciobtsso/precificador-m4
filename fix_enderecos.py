# fix_enderecos.py
import requests
from sqlalchemy import text
from app import create_app, db

# cria o app e entra no contexto
app = create_app()

with app.app_context():
    print("=== PROCESSANDO UM LOTE DE 100 ===")

    rows = db.session.execute(text("""
        SELECT id, cliente_id, cep
        FROM clientes_enderecos
        WHERE (cep IS NOT NULL AND btrim(cep) <> '')
          AND (logradouro IS NULL OR btrim(logradouro) = '')
          AND ignorado = FALSE
        ORDER BY id
        LIMIT 100
    """)).fetchall()

    if not rows:
        print("Nenhum registro restante para processar.")
    else:
        atualizados = 0
        ignorados = 0
        falhas = 0
        for r in rows:
            cep = r.cep.replace("-", "").replace(".", "").strip()
            if len(cep) == 8 and cep.isdigit():
                try:
                    data = requests.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=5).json()
                    if "erro" not in data and data.get("logradouro"):
                        db.session.execute(text("""
                            UPDATE clientes_enderecos
                            SET logradouro=:logradouro,
                                bairro=:bairro,
                                cidade=:cidade,
                                estado=:estado,
                                updated_at=NOW()
                            WHERE id=:id
                        """), {
                            "logradouro": data.get("logradouro", ""),
                            "bairro": data.get("bairro", ""),
                            "cidade": data.get("localidade", ""),
                            "estado": data.get("uf", ""),
                            "id": r.id
                        })
                        atualizados += 1
                        print(f"[OK] ID {r.id} | Cliente {r.cliente_id} | CEP {cep} atualizado")
                    else:
                        db.session.execute(text("""
                            UPDATE clientes_enderecos
                            SET ignorado=TRUE
                            WHERE id=:id
                        """), {"id": r.id})
                        ignorados += 1
                        print(f"[IGNORADO] ID {r.id} | Cliente {r.cliente_id} | CEP {cep} sem logradouro")
                except Exception as e:
                    falhas += 1
                    print(f"[ERRO] ID {r.id} | Cliente {r.cliente_id} | CEP {cep} → {e}")
            else:
                db.session.execute(text("""
                    UPDATE clientes_enderecos
                    SET ignorado=TRUE
                    WHERE id=:id
                """), {"id": r.id})
                ignorados += 1
                print(f"[IGNORADO] ID {r.id} | Cliente {r.cliente_id} | CEP inválido: {r.cep}")

        db.session.commit()
        print(f"\nResumo do lote → Atualizados: {atualizados} | Ignorados: {ignorados} | Falhas: {falhas}")
