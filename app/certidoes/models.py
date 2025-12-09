# app/certidoes/models.py

import enum
from datetime import datetime

from app.extensions import db


class CertidaoTipo(enum.Enum):
    ESTADUAL_TJPI = "estadual_tjpi"       # TJPI – Estadual (Criminal + Auditoria Militar)
    MILITAR_STM = "militar_stm"           # STM – Certidão Negativa de Crimes Militares
    ELEITORAL_TSE = "eleitoral_tse"       # TSE – Crimes Eleitorais
    FEDERAL_TRF1 = "federal_trf1"         # TRF1 – Criminal Federal (PI)


class CertidaoStatus(enum.Enum):
    PENDENTE = "pendente"         # criada, aguardando automação/analista
    EM_PROCESSO = "em_processo"   # automação em execução
    EMITIDA = "emitida"           # pdf obtido
    ERRO = "erro"                 # erro na automação
    CANCELADA = "cancelada"       # não será mais emitida


class Certidao(db.Model):
    __tablename__ = "certidoes"

    id = db.Column(db.Integer, primary_key=True)

    cliente_id = db.Column(
        db.Integer,
        db.ForeignKey("clientes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tipo = db.Column(
        db.Enum(CertidaoTipo, name="certidao_tipo_enum"),
        nullable=False,
        index=True,
    )

    status = db.Column(
        db.Enum(CertidaoStatus, name="certidao_status_enum"),
        nullable=False,
        default=CertidaoStatus.PENDENTE,
        index=True,
    )

    data_solicitacao = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    data_emissao = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    validade_ate = db.Column(
        db.Date,
        nullable=True,
        index=True,
    )

    url_portal = db.Column(
        db.String(255),
        nullable=True,
        doc="URL base do portal usado para emissão",
    )

    arquivo_storage_key = db.Column(
        db.String(255),
        nullable=True,
        unique=True,
        doc="Chave/caminho no R2 ou outro storage para o PDF da certidão",
    )

    observacoes = db.Column(db.Text, nullable=True)

    criado_em = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    atualizado_em = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # 👇 AJUSTE AQUI: tabela correta é "users", não "usuarios"
    criado_por_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    # RELACIONAMENTOS
    cliente = db.relationship(
        "Cliente",
        back_populates="certidoes",
    )

    def label_tipo(self) -> str:
        mapping = {
            CertidaoTipo.ESTADUAL_TJPI: "Estadual TJPI (Criminal + Auditoria Militar)",
            CertidaoTipo.MILITAR_STM: "Crimes Militares – STM",
            CertidaoTipo.ELEITORAL_TSE: "Crimes Eleitorais – TSE",
            CertidaoTipo.FEDERAL_TRF1: "Criminal Federal – TRF1 (1ª Região)",
        }
        return mapping.get(self.tipo, self.tipo.value)

    def label_status(self) -> str:
        mapping = {
            CertidaoStatus.PENDENTE: "Pendente",
            CertidaoStatus.EM_PROCESSO: "Em processo",
            CertidaoStatus.EMITIDA: "Emitida",
            CertidaoStatus.ERRO: "Erro",
            CertidaoStatus.CANCELADA: "Cancelada",
        }
        return mapping.get(self.status, self.status.value)
