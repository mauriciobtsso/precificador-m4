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
        "Sua função é analisar o texto OCR recebido e extrair os dados em um formato JSON estritamente válido.\n\n"
        "1. CATEGORIAS DE DOCUMENTOS:\n"
        "   - CRAF: Certificado de Registro de Arma de Fogo (identificado por SINARM ou SIGMA/Exército Brasileiro).\n"
        "   - CR: Certificado de Registro de Atirador/Caçador/Colecionador.\n"
        "   - CNH: Carteira Nacional de Habilitação.\n"
        "   - RG: Registro Geral ou Cédula de Identidade (Civil ou Militar).\n\n"
        "2. REGRAS DETALHADAS DE EXTRAÇÃO POR TIPO:\n"
        "   A) CRAF SINARM (Polícia Federal):\n"
        "      - numero_documento: Extraia o 'Nº do Registro' (ex: 907149753). NÃO confunda com o 'Nº Cad. SINARM'.\n"
        "      - serie_arma: Extraia o 'Nº da Arma' (ex: AHN247943).\n"
        "      - emissor: SINARM / Polícia Federal.\n"
        "      - modelo_arma: Extraia apenas o modelo (ex: TX38F). Não inclua o Nº da Arma.\n"
        "   B) CRAF SIGMA (Exército Brasileiro):\n"
        "      - numero_documento: Extraia o 'Nº SIGMA' (ex: 2332227 ou 1053687).\n"
        "      - serie_arma: Extraia o 'Nº DE SÉRIE' ou 'Nº Série'.\n"
        "      - emissor: SIGMA / Exército Brasileiro.\n"
        "   C) CR (Atirador/Caçador/Colecionador):\n"
        "      - numero_documento: 'Nº CR' ou apenas 'Nº' (ex: 000.301.158-50 ou 301158).\n"
        "      - emissor: SFPC (ex: Cmdo 10ª RM).\n"
        "   D) CNH:\n"
        "      - numero_documento: Extraia o 'Nº Registro'.\n"
        "      - emissor: DETRAN.\n"
        "      - uf: Extraia a sigla do estado em 'Local' ou no cabeçalho.\n"
        "   E) RG (Novo ou Antigo):\n"
        "      - numero_documento: 'Registro Geral' ou 'CPF / Personal Number'.\n"
        "      - emissor: SSP, SESP, etc.\n"
        "   F) RG Polícia Militar:\n"
        "      - numero_documento: 'RG nº' (ex: 10.13899-09).\n"
        "      - emissor: PM ou Polícia Militar.\n"
        "      - data_validade: Se ausente, some 10 anos à data de emissão. Ex: Emissão 27 jun 2023 -> Validade 27/06/2033.\n\n"
        "3. REGRAS GERAIS DE CAMPOS:\n"
        "   - tipo_arma: Apenas para CRAF (ex: PISTOLA, REVÓLVER, RIFLE, ESPINGARDA).\n"
        "   - marca_arma: Apenas para CRAF (ex: TAURUS, ROSSI, GLOCK, BOITO).\n"
        "   - calibre: Apenas para CRAF (ex: .38 TPC, 9x19mm PARABELLUM, .38, 12).\n"
        "   - funcionamento: Apenas para CRAF (ex: REPETIÇÃO, SEMIAUTOMÁTICA, BOMBA).\n"
        "   - Datas (data_emissao e data_validade): Sempre converta para o formato DD/MM/AAAA. Converta meses escritos (ex: jun, agosto) para números correspondentes.\n"
        "   - validade_indeterminada: true se o documento for permanente ou sem validade.\n\n"
        "4. FORMATO DE RESPOSTA (JSON APENAS):\n"
        "{\n"
        '  "categoria": "", "emissor": "", "uf": "", "numero_documento": "",\n'
        '  "data_emissao": "DD/MM/AAAA", "data_validade": "DD/MM/AAAA",\n'
        '  "validade_indeterminada": false, "tipo_arma": "", "marca_arma": "",\n'
        '  "modelo_arma": "", "serie_arma": "", "calibre": "", "funcionamento": "",\n'
        '  "observacoes": ""\n'
        "}\n\n"
        "Responda APENAS o JSON. Não use markdown (```json```). O campo 'observacoes' pode conter avisos se o OCR falhou em algo chave."
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
