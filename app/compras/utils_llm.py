# ============================================================
# MÓDULO: COMPRAS — Integração com LLM (Groq 70B para NF-e)
# ============================================================

from app.compras.llm_nf import call_nf_llm as call_llm_model
import json
import re


def analisar_nf_xml_conteudo(xml_texto: str):
    """
    Usa o modelo Groq 70B (isolado) para interpretar o XML de NF-e.
    - Extrai apenas as tags <det> (itens) para reduzir tamanho;
    - Retorna lista de produtos padronizada;
    - Suporta variações de formato de resposta do LLM.
    """

    # ============================================================
    # 1️⃣ — Extrai apenas as tags <det> (itens)
    # ============================================================
    blocos = re.findall(r"<det[^>]*>.*?</det>", xml_texto, flags=re.DOTALL)
    xml_reduzido = "\n".join(blocos) or xml_texto

    # ============================================================
    # 2️⃣ — Monta o prompt para o modelo Groq
    # ============================================================
    prompt = f"""
    Você é um especialista em leitura de notas fiscais eletrônicas brasileiras (NF-e),
    especialmente de produtos controlados como armas, munições e acessórios.

    Leia atentamente o XML abaixo (somente os blocos <det> dos produtos) e devolva
    uma lista JSON contendo todos os itens descritos na nota.

    ⚠️ Importante:
    - Responda **somente com JSON válido**.
    - Não inclua explicações nem texto fora do JSON.
    - Se algum campo não existir, deixe-o em branco.

    Cada item deve conter:
    - descricao
    - marca
    - modelo
    - calibre
    - lote (ou número de série, se houver)
    - quantidade
    - valor_unitario

    Exemplo:
    [
      {{
        "descricao": "PISTOLA TAURUS G3 TORO 9MM",
        "marca": "TAURUS",
        "modelo": "G3 TORO",
        "calibre": "9MM",
        "lote": "AGM012345",
        "quantidade": 2,
        "valor_unitario": 3712.90
      }},
      {{
        "descricao": "MUNIÇÃO CBC .38 SPL OGIVAL",
        "marca": "CBC",
        "modelo": "",
        "calibre": ".38 SPL",
        "lote": "GUO74",
        "quantidade": 500,
        "valor_unitario": 4.10
      }}
    ]

    XML (parcial da NF):
    {xml_reduzido}
    """

    # ============================================================
    # 3️⃣ — Chamada ao modelo LLM (Groq 70B)
    # ============================================================
    resposta = call_llm_model(prompt)

    # ============================================================
    # 4️⃣ — Flexibiliza o formato de resposta
    # ============================================================
    try:
        if isinstance(resposta, list):
            return resposta

        if isinstance(resposta, dict):
            # tenta encontrar as principais chaves
            for key in ["itens", "produtos", "items", "products", "data"]:
                if key in resposta:
                    return resposta[key]

            # pode ter vindo um único produto
            if all(k in resposta for k in ["descricao", "marca", "valor_unitario"]):
                return [resposta]

        if isinstance(resposta, str):
            data = json.loads(resposta)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                for key in ["itens", "produtos", "items", "products"]:
                    if key in data:
                        return data[key]
                return [data]

    except Exception as e:
        raise RuntimeError(f"Erro ao processar resposta do LLM: {e}")

    raise RuntimeError("Resposta do LLM fora do formato esperado.")
