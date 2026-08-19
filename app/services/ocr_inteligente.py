# =====================================
# OCR INTELIGENTE (via Groq LLM)
# =====================================
# Interpreta textos OCR com Llama 3.1-8B (Groq)
# Retorna um dicionário padronizado com campos de documento.

import os
import json
import re
import requests
from datetime import datetime


# =====================================
# Configurações
# =====================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

if not GROQ_API_KEY:
    raise RuntimeError("A variável de ambiente GROQ_API_KEY não está configurada.")


# =====================================
# Função utilitária: valida e inverte datas se necessário
# =====================================

def _corrigir_datas(data_emissao: str, data_validade: str) -> tuple[str, str]:
    """Corrige inversão de datas, caso a validade venha anterior à emissão."""
    def parse(d):
        try:
            return datetime.strptime(d, "%d/%m/%Y")
        except Exception:
            return None

    de = parse(data_emissao)
    dv = parse(data_validade)

    # Caso ambas sejam válidas e a validade seja anterior à emissão → inverter
    if de and dv and dv < de:
        data_emissao, data_validade = data_validade, data_emissao

    return data_emissao, data_validade


# =====================================
# Função principal
# =====================================

def interpretar_documento(texto_ocr: str) -> dict:
    """
    Envia texto OCR bruto para a LLM da Groq e retorna
    um dicionário padronizado:
    {
        "categoria": "CR / CRAF / CNH / RG / CPF / OUTRO",
        "emissor": "SIGMA / SINARM / DETRAN / SSP / RECEITA FEDERAL / OUTRO",
        "numero_documento": "123456/2024",
        "data_emissao": "DD/MM/AAAA",
        "data_validade": "DD/MM/AAAA",
        "validade_indeterminada": false,
        "observacoes": ""
    }
    """

    if not texto_ocr or len(texto_ocr.strip()) < 20:
        return {
            "engine": GROQ_MODEL,
            "categoria": "OUTRO",
            "emissor": "",
            "numero_documento": "",
            "data_emissao": "",
            "data_validade": "",
            "validade_indeterminada": False,
            "observacoes": "Texto OCR muito curto ou ilegível."
        }

    # ============================
    # Instrução do sistema
    # ============================
    prompt_sistema = (
        "Você é um assistente especialista em leitura de documentos brasileiros (CR, CRAF, CNH, RG, CPF).\n"
        "Analise o texto OCR e retorne um JSON estritamente válido seguindo estas regras:\n\n"
        "1. CATEGORIAS:\n"
        "   - CRAF: Certificado de Registro de Arma de Fogo (SINARM ou SIGMA).\n"
        "   - CR: Certificado de Registro de Atirador/Caçador/Colecionador.\n"
        "   - CNH: Carteira Nacional de Habilitação.\n"
        "   - RG: Registro Geral ou Cédula de Identidade (Civil ou Militar).\n\n"
        "2. REGRAS DE CAMPOS:\n"
        "   - numero_documento: Número principal (Registro SINARM, SIGMA, CR, CNH ou RG).\n"
        "   - emissor: Órgão expedidor (ex: SIGMA, SINARM, DETRAN, SSP, PMPI, EB).\n"
        "   - uf: Sigla do estado emissor (ex: PI, SP, RJ).\n"
        "   - tipo_arma: Apenas para CRAF (ex: Pistola, Revólver, Carabina).\n"
        "   - marca_arma: Apenas para CRAF (ex: Taurus, Rossi, Glock).\n"
        "   - modelo_arma: Apenas para CRAF. Extraia apenas o nome do modelo (ex: G3, TX38F). "
        "     NUNCA inclua números de série ou rótulos como 'Nº da Arma' aqui.\n"
        "   - serie_arma: Número de série gravado na arma.\n"
        "   - funcionamento: Apenas para CRAF (ex: Semiautomática, Repetição).\n"
        "   - calibre: Ex: .380, 9mm, .40.\n"
        "   - validade_indeterminada: true se o documento não tiver validade ou for permanente.\n"
        "   - data_validade: Se ausente em RG Militar, calcule como 10 anos após a data de emissão.\n\n"
        "3. FORMATO DE RESPOSTA (JSON APENAS):\n"
        "{\n"
        '  "categoria": "", "emissor": "", "uf": "", "numero_documento": "",\n'
        '  "data_emissao": "DD/MM/AAAA", "data_validade": "DD/MM/AAAA",\n'
        '  "validade_indeterminada": false, "tipo_arma": "", "marca_arma": "",\n'
        '  "modelo_arma": "", "serie_arma": "", "calibre": "", "funcionamento": "",\n'
        '  "observacoes": ""\n'
        "}\n\n"
        "Responda APENAS o JSON, sem explicações ou ```json```."
    )

    # ============================
    # Payload para Groq
    # ============================
    payload = {
        "model": GROQ_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": texto_ocr}
        ]
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # ============================
    # Requisição
    # ============================
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )

        if r.status_code != 200:
            raise RuntimeError(f"Erro {r.status_code}: {r.text}")

        content = r.json()["choices"][0]["message"]["content"].strip()

        # ============================
        # Sanitização de resposta
        # ============================
        content = re.sub(r"```(?:json)?", "", content)
        content = content.replace("```", "").strip()

        # Extrai trecho JSON bruto
        if not content.strip().startswith("{"):
            start = content.find("{")
            end = content.rfind("}") + 1
            content = content[start:end]

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            raise ValueError(f"Falha ao decodificar JSON: {content[:200]}")

        # ============================
        # Normaliza e corrige
        # ============================
        padrao = {
            "categoria": "OUTRO",
            "emissor": "",
            "uf": "",
            "numero_documento": "",
            "data_emissao": "",
            "data_validade": "",
            "validade_indeterminada": False,
            "tipo_arma": "",
            "marca_arma": "",
            "modelo_arma": "",
            "serie_arma": "",
            "calibre": "",
            "funcionamento": "",
            "observacoes": ""
        }

        padrao.update({k: v for k, v in data.items() if k in padrao})

        # Corrige inversão de datas, se necessário
        padrao["data_emissao"], padrao["data_validade"] = _corrigir_datas(
            padrao.get("data_emissao", ""),
            padrao.get("data_validade", "")
        )

        padrao["engine"] = GROQ_MODEL
        return padrao

    except Exception as e:
        return {
            "engine": GROQ_MODEL,
            "categoria": "OUTRO",
            "emissor": "",
            "numero_documento": "",
            "data_emissao": "",
            "data_validade": "",
            "validade_indeterminada": False,
            "observacoes": f"Erro no processamento via Groq: {e}"
        }


# =====================================
# Teste isolado
# =====================================
if __name__ == "__main__":
    texto_exemplo = """
    REPÚBLICA FEDERATIVA DO BRASIL
    MINISTÉRIO DA DEFESA - EXÉRCITO BRASILEIRO
    CERTIFICADO DE REGISTRO N° 123456/2024
    Nome: ADÃO ALMEIDA SILVA
    CPF: 864.348.962-04
    Emissão: 10/03/2024
    Validade: 10/03/2029
    """
    resultado = interpretar_documento(texto_exemplo)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
