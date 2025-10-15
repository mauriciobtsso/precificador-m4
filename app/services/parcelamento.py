# app/services/parcelamento.py
from typing import List, Tuple, Optional
from app.produtos.models import Produto
from app.models import Taxa
import app.utils.parcelamento as parc
from app.utils.whatsapp import gerar_mensagem_whatsapp


def _valor_base_do_produto(produto: Produto) -> float:
    """
    Mesma regra usada nas rotas:
    valor_base = produto.preco_final or produto.preco_a_vista or 0.0
    (Todo cálculo de IPI, DIFAL, frete, etc. já está refletido no preco_final.)
    """
    return produto.preco_final or produto.preco_a_vista or 0.0


def gerar_linhas_por_valor(valor_base: float) -> List[dict]:
    """
    Gera as linhas de parcelamento para um valor avulso (modo 'rápido'),
    usando exatamente o gerador já utilizado hoje e as taxas do BD.
    """
    taxas = Taxa.query.order_by(Taxa.numero_parcelas).all()
    return parc.gerar_linhas_parcelas(valor_base, taxas)


def gerar_linhas_por_produto(produto: Produto) -> Tuple[float, List[dict]]:
    """
    Gera as linhas de parcelamento para um Produto.
    Reaproveita o mesmo 'valor_base' que a rota já usa hoje
    (preco_final -> preco_a_vista -> 0.0) e o mesmo gerador de linhas.
    """
    valor_base = _valor_base_do_produto(produto)
    linhas = gerar_linhas_por_valor(valor_base)
    return valor_base, linhas


def gerar_texto_whatsapp(
    produto: Optional[Produto],
    valor_base: float,
    linhas: List[dict]
) -> str:
    """
    Composição do texto via utilitário já existente.
    """
    return gerar_mensagem_whatsapp(produto, valor_base, linhas)
