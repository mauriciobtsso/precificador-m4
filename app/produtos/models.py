# ======================
# MODELO — PRODUTO (VERSÃO E-COMMERCE M4 - QAP TERESINA)
# ======================

from app import db
from sqlalchemy import func, Index, event
from datetime import datetime
import pytz
import re
from flask_login import current_user
from decimal import Decimal, InvalidOperation

# Importações auxiliares
from app.utils.datetime import now_local
from app.produtos.categorias.models import CategoriaProduto
from app.produtos.configs.models import (
    MarcaProduto,
    CalibreProduto,
    TipoProduto,
    FuncionamentoProduto,
)

# ======================================================
# MODELO PRINCIPAL: PRODUTO
# ======================================================
class Produto(db.Model):
    __tablename__ = "produtos"
    __table_args__ = (
        Index("idx_produto_nome", "nome"),
        Index("idx_produto_codigo", "codigo"),
        Index("idx_produto_categoria", "categoria_id"),
        Index("idx_produto_marca", "marca_id"),
        Index("idx_produto_calibre", "calibre_id"),
        Index("idx_produto_tipo", "tipo_id"),
        Index("idx_produto_slug", "slug"),
    )

    id = db.Column(db.Integer, primary_key=True)
    foto_url = db.Column(db.String(512), nullable=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # NOME 1: Nome Interno (Administrativo/Fiscal)
    nome = db.Column(db.String(255), nullable=False, index=True)
    
    descricao = db.Column(db.Text, nullable=True)

    # --- CAMPOS DE E-COMMERCE E VISIBILIDADE ---
    # NOME 2: Nome de Exibição na Loja (Amigável)
    nome_comercial = db.Column(db.String(255), nullable=True) 
    
    slug = db.Column(db.String(255), unique=True, index=True) 
    visivel_loja = db.Column(db.Boolean, default=False, index=True)
    estoque_disponivel = db.Column(db.Integer, default=0)
    
    # Flags para Carrosséis Estilo Mahrte
    destaque_home = db.Column(db.Boolean, default=False)
    eh_lancamento = db.Column(db.Boolean, default=False)
    eh_outdoor = db.Column(db.Boolean, default=False) 
    
    # --- CONTROLE DE VENDA (HÍBRIDO) ---
    requer_documentacao = db.Column(db.Boolean, default=True, index=True) 

    # --- CAMPOS DE SEO (NOME 3: ABA DO NAVEGADOR / GOOGLE) ---
    meta_title = db.Column(db.String(120), nullable=True) # Aumentado para segurança
    meta_description = db.Column(db.String(250), nullable=True) # Aumentado para 250 conforme solicitado
    tags_palavras_chave = db.Column(db.String(255), nullable=True)

    # --- CONTEÚDO PÚBLICO (SITE) ---
    descricao_comercial = db.Column(db.Text, nullable=True) # Resumo breve
    descricao_longa = db.Column(db.Text, nullable=True) # HTML do Summernote
    especificacoes_tecnicas = db.Column(db.JSON, nullable=True)

    # --- RELACIONAMENTOS ---
    categoria_id = db.Column(db.Integer, db.ForeignKey("categoria_produto.id"), index=True)
    categoria = db.relationship("CategoriaProduto", backref="produtos")

    marca_id = db.Column(db.Integer, db.ForeignKey("marca_produto.id"), nullable=True, index=True)
    marca_rel = db.relationship("MarcaProduto", backref="produtos")

    calibre_id = db.Column(db.Integer, db.ForeignKey("calibre_produto.id"), nullable=True, index=True)
    calibre_rel = db.relationship("CalibreProduto", backref="produtos")

    tipo_id = db.Column(db.Integer, db.ForeignKey("tipo_produto.id"), nullable=True, index=True)
    tipo_rel = db.relationship("TipoProduto", backref="produtos")

    funcionamento_id = db.Column(db.Integer, db.ForeignKey("funcionamento_produto.id"), nullable=True)
    funcionamento_rel = db.relationship("FuncionamentoProduto", backref="produtos")

    # --- FINANCEIRO E PRECIFICAÇÃO ---
    preco_fornecedor = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    desconto_fornecedor = db.Column(db.Numeric(5, 2), nullable=True, default=0)
    frete = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    margem = db.Column(db.Numeric(5, 2), nullable=True, default=0)
    ipi = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    ipi_tipo = db.Column(db.String(10), nullable=True, default="%")
    difal = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    imposto_venda = db.Column(db.Numeric(10, 2), nullable=True, default=0)

    # --- CAMPOS DE PROMOÇÃO ---
    promo_ativada = db.Column(db.Boolean, default=False, index=True)
    promo_preco_fornecedor = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    promo_data_inicio = db.Column(db.DateTime(timezone=True), nullable=True)
    promo_data_fim = db.Column(db.DateTime(timezone=True), nullable=True)

    custo_total = db.Column(db.Numeric(12, 2), nullable=True, default=0)
    preco_a_vista = db.Column(db.Numeric(12, 2), nullable=True, default=0)
    lucro_liquido_real = db.Column(db.Numeric(12, 2), nullable=True, default=0)

    lucro_alvo = db.Column(db.Numeric(12, 2), nullable=True)
    preco_final = db.Column(db.Numeric(12, 2), nullable=True)

    criado_em = db.Column(db.DateTime(timezone=True), default=now_local, index=True)
    atualizado_em = db.Column(db.DateTime(timezone=True), onupdate=now_local, default=now_local, index=True)

    historicos = db.relationship("ProdutoHistorico", back_populates="produto", cascade="all, delete-orphan", lazy=True)

    def calcular_precos(self):
        agora = now_local()
        preco_base = float(self.preco_fornecedor or 0)
        em_oferta = False

        if self.promo_ativada and self.promo_preco_fornecedor and self.promo_data_inicio and self.promo_data_fim:
            try:
                p_promo = float(self.promo_preco_fornecedor)
                if p_promo > 0 and self.promo_data_inicio <= agora <= self.promo_data_fim:
                    preco_base = p_promo
                    em_oferta = True
            except (ValueError, TypeError):
                pass 

        desconto = float(self.desconto_fornecedor or 0)
        frete = float(self.frete or 0)
        margem = float(self.margem or 0)
        imposto_venda = float(self.imposto_venda or 0)
        difal = float(self.difal or 0)
        ipi = float(self.ipi or 0)
        ipi_tipo = (self.ipi_tipo or "%").strip()

        base = preco_base * (1 - (desconto / 100))
        if ipi_tipo == "%_dentro":
            base_sem_ipi = base / (1 + (ipi / 100))
            valor_ipi = base - base_sem_ipi
        elif ipi_tipo == "%":
            valor_ipi = base * (ipi / 100)
        else:
            valor_ipi = ipi

        valor_difal = (base - valor_ipi + frete) * (difal / 100)
        custo_total = base + valor_difal + frete

        preco_final = float(self.preco_final or 0)
        lucro_alvo = float(self.lucro_alvo or 0)
        if preco_final <= 0:
            if lucro_alvo > 0:
                preco_final = (custo_total + lucro_alvo) / (1 - (imposto_venda / 100))
            elif margem > 0:
                preco_final = custo_total / (1 - (margem / 100))
            else:
                preco_final = custo_total

        imposto_venda_valor = preco_final * (imposto_venda / 100)
        lucro_liquido = preco_final - custo_total - imposto_venda_valor

        self.custo_total = round(custo_total, 2)
        self.preco_a_vista = round(preco_final, 2)
        self.lucro_liquido_real = round(lucro_liquido, 2)

        return {
            "custo_total": self.custo_total,
            "preco_a_vista": self.preco_a_vista,
            "lucro_liquido_real": self.lucro_liquido_real,
            "em_oferta": em_oferta
        }

    def __repr__(self):
        return f"<Produto {self.codigo} - {self.nome}>"

# Listener de Slug
def gera_slug_automatico(target, value, oldvalue, initiator):
    if value and (not target.slug or value != oldvalue):
        texto = value.lower().strip()
        texto = re.sub(r'[áàâãä]', 'a', texto); texto = re.sub(r'[éèêë]', 'e', texto)
        texto = re.sub(r'[íìîï]', 'i', texto); texto = re.sub(r'[óòôõö]', 'o', texto)
        texto = re.sub(r'[úùûü]', 'u', texto); texto = re.sub(r'[ç]', 'c', texto)
        texto = re.sub(r'[^\w\s-]', '', texto)
        texto = re.sub(r'[\s_-]+', '-', texto)
        target.slug = texto

event.listen(Produto.nome, 'set', gera_slug_automatico, retval=False)

class ProdutoHistorico(db.Model):
    __tablename__ = "produto_historico"
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False, index=True)
    campo = db.Column(db.String(100), nullable=False)
    valor_antigo = db.Column(db.Text)
    valor_novo = db.Column(db.Text)
    usuario_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    usuario_nome = db.Column(db.String(120))
    data_modificacao = db.Column(db.DateTime(timezone=True), default=now_local, index=True)
    origem = db.Column(db.String(20), nullable=False, default="manual", index=True)
    produto = db.relationship("Produto", back_populates="historicos")