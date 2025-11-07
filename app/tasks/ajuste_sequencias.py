# ============================================================
# MÓDULO: AJUSTE AUTOMÁTICO DE SEQUÊNCIAS — Produtos e Configs
# ============================================================

from sqlalchemy import text
from flask import current_app
from app import db
from datetime import datetime

TABELAS_SEQUENCIAS = [
    "produtos",
    "categoria_produto",
    "marca_produto",
    "tipo_produto",
    "calibre_produto",
    "funcionamento_produto",
]

def corrigir_todas_as_sequencias():
    """Varre e corrige as sequências de todas as tabelas relacionadas a produtos."""
    total_corrigidas = 0
    falhas = []
    for tabela in TABELAS_SEQUENCIAS:
        try:
            sql = text(f"""
                SELECT setval(
                    pg_get_serial_sequence('{tabela}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {tabela}), 1),
                    TRUE
                );
            """)
            db.session.execute(sql)
            db.session.commit()
            current_app.logger.info(f"[AUTOSEQ] Sequência corrigida para '{tabela}' ✅")
            total_corrigidas += 1
        except Exception as e:
            db.session.rollback()
            falhas.append((tabela, str(e)))
            current_app.logger.error(f"[AUTOSEQ] Falha ao corrigir sequência de '{tabela}': {e}")

    resumo = f"{total_corrigidas} sequência(s) corrigida(s) às {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    if falhas:
        resumo += f" — Falhas em: {', '.join(t for t, _ in falhas)}"
    current_app.logger.info(f"[AUTOSEQ] {resumo}")
    return {"corrigidas": total_corrigidas, "falhas": falhas}
