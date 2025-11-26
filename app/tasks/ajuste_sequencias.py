# ============================================================
# MÓDULO: AJUSTE AUTOMÁTICO DE SEQUÊNCIAS — Todas as Tabelas
# ============================================================

from sqlalchemy import text
from flask import current_app
from app import db
from datetime import datetime

# Lista completa de tabelas do sistema que possuem campo 'id' auto-incremento
TABELAS_SEQUENCIAS = [
    # Produtos e Configs
    "produtos",
    "produto_embalagens", # Se já tiver criado
    "categoria_produto",
    "marca_produto",
    "tipo_produto",
    "calibre_produto",
    "funcionamento_produto",
    "produto_historico",
    
    # Clientes
    "clientes",
    "clientes_enderecos",
    "clientes_contatos",
    "documentos",
    "armas",
    "comunicacoes",
    "processos",
    
    # Vendas
    "vendas",
    "itens_venda",
    "vendas_anexos",
    
    # Estoque
    "estoque_itens",
    
    # Sistema
    "users",
    "configuracoes",
    "taxas"
]

def corrigir_todas_as_sequencias():
    """Varre e corrige as sequências de todas as tabelas listadas."""
    total_corrigidas = 0
    falhas = []
    
    print(f"🔄 [AUTOSEQ] Iniciando correção de sequências para {len(TABELAS_SEQUENCIAS)} tabelas...")
    
    for tabela in TABELAS_SEQUENCIAS:
        try:
            # Verifica se a tabela existe antes de tentar corrigir
            check_sql = text("SELECT to_regclass(:tabela)")
            result = db.session.execute(check_sql, {"tabela": tabela}).scalar()
            
            if not result:
                continue # Tabela não existe ainda (ex: migração pendente), pula

            # Comando PostgreSQL para resetar a sequência para o MAX(id) + 1
            sql = text(f"""
                SELECT setval(
                    pg_get_serial_sequence('{tabela}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {tabela}), 1) + 1,
                    FALSE
                );
            """)
            db.session.execute(sql)
            db.session.commit()
            total_corrigidas += 1
        except Exception as e:
            db.session.rollback()
            # Ignora erros de tabelas que talvez não usem sequence padrão ou não existam
            falhas.append((tabela, str(e)))
            # current_app.logger.error(f"[AUTOSEQ] Erro em '{tabela}': {e}")

    resumo = f"✅ {total_corrigidas} sequências sincronizadas."
    if falhas:
        print(f"⚠️ Falhas (ignoradas se tabela não existir): {len(falhas)}")
    
    print(resumo)
    return {"corrigidas": total_corrigidas, "falhas": falhas}