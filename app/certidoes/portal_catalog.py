from __future__ import annotations

import re
from typing import Any

PORTAIS = {
    "stm": {"nome": "STM", "descricao": "Certidão negativa militar", "url": "https://www.stm.jus.br/servicos-ao-cidadao/atendimentoaocidadao/certidao-negativa?view=default"},
    "mppi": {"nome": "MPPI", "descricao": "Certidão negativa estadual", "url": "https://www.mppi.mp.br/consulta-publica/certidao_negativa/index"},
    "mpf": {"nome": "MPF", "descricao": "Certidão negativa federal", "url": "https://aplicativos.mpf.mp.br/ouvidoria/app/cidadao/certidao"},
    "tjpi": {"nome": "TJPI", "descricao": "Certidão unificada", "url": "https://europa.tjpi.jus.br/certidao/unificada"},
    "tse": {"nome": "TSE", "descricao": "Certidão eleitoral", "url": "https://www.tse.jus.br/servicos-eleitorais/autoatendimento-eleitoral#/"},
    "cjf": {"nome": "CJF", "descricao": "Certidão negativa federal", "url": "https://www.cjf.jus.br/cjf/certidao-negativa"},
    "pc_pi": {"nome": "PC-PI", "descricao": "Solicitação de certidão policial", "url": "https://portal.pi.gov.br/pc/formulario-solicitacao-certidao/"},
}


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def cliente_payload(cliente) -> dict[str, Any]:
    endereco = next((item for item in (cliente.enderecos or []) if item.tipo == "residencial"), None)
    contatos = {str(item.tipo or "").lower(): item.valor for item in (cliente.contatos or []) if item.valor}
    return {
        "id": cliente.id,
        "nome": cliente.nome or "",
        "nome_completo": cliente.nome or "",
        "cpf": _digits(cliente.documento),
        "documento": cliente.documento or "",
        "rg": cliente.rg or "",
        "rg_emissor": cliente.rg_emissor or "",
        "data_nascimento": cliente.data_nascimento.isoformat() if cliente.data_nascimento else "",
        "estado_civil": cliente.estado_civil or "",
        "profissao": cliente.profissao or "",
        "nome_pai": cliente.nome_pai or "",
        "nome_mae": cliente.nome_mae or "",
        "email": contatos.get("email", ""),
        "telefone": contatos.get("telefone") or contatos.get("celular") or "",
        "celular": contatos.get("celular", ""),
        "cep": _digits(getattr(endereco, "cep", "")),
        "logradouro": getattr(endereco, "logradouro", "") or "",
        "endereco": getattr(endereco, "logradouro", "") or "",
        "numero": getattr(endereco, "numero", "") or "",
        "complemento": getattr(endereco, "complemento", "") or "",
        "bairro": getattr(endereco, "bairro", "") or "",
        "cidade": getattr(endereco, "cidade", "") or "",
        "estado": getattr(endereco, "estado", "") or "",
        "uf": getattr(endereco, "estado", "") or "",
    }
