"""Ativar pg_trgm e criar índices GIN para busca fuzzy

Revision ID: 20260802_fuzzy_search_trgm
Revises: ffeeb56c244c
Create Date: 2026-08-02 23:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260802_fuzzy_search_trgm'
down_revision = 'ffeeb56c244c'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Ativar a extensão pg_trgm
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    
    # 2. Criar índices GIN nas colunas de busca da tabela produtos
    # Usamos gin_trgm_ops para permitir busca por similaridade de trigrama
    op.execute("CREATE INDEX IF NOT EXISTS idx_produtos_nome_trgm ON produtos USING gin (nome gin_trgm_ops);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_produtos_nome_comercial_trgm ON produtos USING gin (nome_comercial gin_trgm_ops);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_produtos_codigo_trgm ON produtos USING gin (codigo gin_trgm_ops);")

def downgrade():
    # Remover índices
    op.execute("DROP INDEX IF EXISTS idx_produtos_nome_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_produtos_nome_comercial_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_produtos_codigo_trgm;")
    
    # Opcional: não removemos a extensão pois outros recursos podem depender dela
    # op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
