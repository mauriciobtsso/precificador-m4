# =======================================================
# MÓDULO: app/vendas/models.py
# Estrutura revisada - Vendas 2.0 (Armas, Munições e Acessórios)
# =======================================================

from datetime import datetime, date
from app.extensions import db

# =========================
# VENDA (PEDIDO)
# =========================
class Venda(db.Model):
    __tablename__ = "vendas"

    id = db.Column(db.Integer, primary_key=True)

    # --- Relacionamento principal ---
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)

    # --- Identificação / relacionamento ---
    vendedor = db.Column(db.String(100))
    caixa = db.Column(db.String(100))

    # --- Datas principais ---
    data_abertura = db.Column(db.DateTime, default=datetime.now)
    data_fechamento = db.Column(db.DateTime)
    data_quitacao = db.Column(db.DateTime)
    data_cancelamento = db.Column(db.DateTime)

    # --- Status Básicos ---
    status = db.Column(db.String(50)) # aberto, orcamento, concluido, cancelado
    status_financeiro = db.Column(db.String(50)) # pendente, pago, parcial
    teve_devolucao = db.Column(db.Boolean, default=False)

    # --- INTEGRAÇÃO 2.0: WORKFLOW DE ARMAS ---
    # Define o fluxo visual (stepper) e as exigências legais
    # Opções: 'arma' (8 etapas), 'municao' (CRAF+Termo), 'livre' (Simples)
    tipo_processo = db.Column(db.String(20), default='livre')

    # Máquina de Estados do Processo Legal
    # Opções: RASCUNHO, ASSINATURA, AUTORIZACAO, CRAF, GT, RETIRADA, CONCLUIDA
    etapa = db.Column(db.String(50), default="RASCUNHO", index=True)

    # Controle de Entrega Física (Cofre)
    data_entrega_efetiva = db.Column(db.DateTime, nullable=True)
    retirado_por = db.Column(db.String(150), nullable=True) # Nome de quem retirou

    # --- Dados financeiros ---
    valor_total = db.Column(db.Numeric(10, 2), default=0.0)
    desconto_valor = db.Column(db.Numeric(10, 2), default=0.0)
    desconto_percentual = db.Column(db.Float, default=0.0)
    valor_recebido = db.Column(db.Numeric(10, 2), default=0.0)
    valor_faltante = db.Column(db.Numeric(10, 2), default=0.0)

    # --- Parcelamento / Crediário ---
    crediario = db.Column(db.Boolean, default=False)
    parcelas_qtd = db.Column(db.Integer)
    parcelas_primeiro_vencimento = db.Column(db.Date)
    parcelas_ultimo_vencimento = db.Column(db.Date)

    # --- Dados fiscais ---
    nf_data = db.Column(db.Date)
    nf_numero = db.Column(db.String(50))
    nf_valor = db.Column(db.Numeric(10, 2))

    # --- Dados auxiliares de cliente (Snapshot) ---
    cliente_nome = db.Column(db.String(200))
    documento_cliente = db.Column(db.String(50))
    tipo_pessoa = db.Column(db.String(20))

    # --- Quantitativo geral ---
    qtd_total_itens = db.Column(db.Integer, default=0)
    observacoes = db.Column(db.Text, nullable=True)

    # --- Controle interno ---
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp()
    )

    # --- Relacionamentos ---
    itens = db.relationship("ItemVenda", backref="venda", lazy=True, cascade="all, delete-orphan")
    cliente = db.relationship("Cliente", back_populates="vendas")
    
    # Novo: Anexos do processo (Contratos, CRAFs, GTs)
    anexos = db.relationship("VendaAnexo", backref="venda", lazy="dynamic", cascade="all, delete-orphan")

    # --- Métodos auxiliares ---
    def calcular_totais(self):
        """Recalcula totais e descontos com base nos itens."""
        if not self.itens:
            self.valor_total = 0
            self.qtd_total_itens = 0
            return

        total = sum(item.valor_total for item in self.itens)
        self.qtd_total_itens = sum(item.quantidade for item in self.itens)
        self.valor_total = round(total, 2)
        
        # Atualiza faltante
        recebido = self.valor_recebido or 0
        desc = self.desconto_valor or 0
        self.valor_faltante = self.valor_total - desc - recebido

    def __repr__(self):
        return f"<Venda {self.id} | Cliente={self.cliente_nome or self.cliente_id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "cliente": self.cliente_nome,
            "documento": self.documento_cliente,
            "vendedor": self.vendedor,
            "status": self.status,
            "etapa": self.etapa,
            "tipo_processo": self.tipo_processo,
            "valor_total": float(self.valor_total or 0),
            "data_abertura": self.data_abertura.strftime("%Y-%m-%d %H:%M") if self.data_abertura else None,
        }


# =========================
# ITEM DE VENDA
# =========================
class ItemVenda(db.Model):
    __tablename__ = "itens_venda"

    id = db.Column(db.Integer, primary_key=True)
    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id", ondelete="CASCADE"), nullable=False)

    # Dados congelados no momento da venda
    produto_nome = db.Column(db.String(200), nullable=False)
    categoria = db.Column(db.String(100))
    quantidade = db.Column(db.Integer, default=1)
    valor_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    valor_total = db.Column(db.Numeric(10, 2), nullable=False)

    sku = db.Column(db.String(50))
    
    # --- RASTREABILIDADE E VÍNCULOS ---
    
    # 1. Qual é o produto no catálogo?
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=True)
    
    # 2. Venda de ARMA (Sai do nosso estoque)
    # Vincula ao Serial específico no cofre
    item_estoque_id = db.Column(db.Integer, db.ForeignKey("estoque_itens.id"), nullable=True)

    # 3. Venda de MUNIÇÃO (Requer CRAF do cliente)
    # Vincula à arma que o cliente já possui (Acervo)
    arma_cliente_id = db.Column(db.Integer, db.ForeignKey("armas.id"), nullable=True)

    # Relacionamentos
    produto = db.relationship("Produto")
    item_estoque = db.relationship("ItemEstoque") 
    arma_cliente = db.relationship("Arma", foreign_keys=[arma_cliente_id])

    def __repr__(self):
        return f"<ItemVenda {self.id} - {self.produto_nome}>"

    def to_dict(self):
        data = {
            "produto": self.produto_nome,
            "categoria": self.categoria,
            "quantidade": self.quantidade,
            "valor_unitario": float(self.valor_unitario or 0),
            "valor_total": float(self.valor_total or 0),
        }
        # Dados extras de rastreabilidade
        if self.item_estoque:
            data["serial"] = self.item_estoque.numero_serie
            data["lote"] = self.item_estoque.lote
        
        if self.arma_cliente:
            data["craf_vinculado"] = f"{self.arma_cliente.modelo} ({self.arma_cliente.numero_serie})"
            
        return data


# =========================
# ANEXOS DA VENDA (WORKFLOW)
# =========================
class VendaAnexo(db.Model):
    __tablename__ = "vendas_anexos"

    id = db.Column(db.Integer, primary_key=True)
    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id", ondelete="CASCADE"), nullable=False)
    
    # Tipos: CONTRATO, IDENTIDADE, AUTORIZACAO, CRAF, GT, TERMO_RETIRADA, OUTROS
    tipo_documento = db.Column(db.String(50), nullable=False)
    
    nome_arquivo = db.Column(db.String(255), nullable=False)
    url_arquivo = db.Column(db.String(500), nullable=False) # URL do R2 ou caminho local
    
    # Metadados extraídos via OCR (Ex: numero do CRAF, validade da GT)
    metadados = db.Column(db.JSON, nullable=True)
    
    criado_em = db.Column(db.DateTime, default=datetime.now)
    enviado_por = db.Column(db.String(100))

    def __repr__(self):
        return f"<Anexo {self.tipo_documento} da Venda {self.venda_id}>"