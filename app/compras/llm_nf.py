# ============================================================
# MÓDULO: COMPRAS — LLM ESPECÍFICO PARA NF-E (com fallback)
# ============================================================
# - Usa GROQ_API_KEY_NF / GROQ_MODEL_NF do .env (sem afetar outros módulos)
# - Faz fallback automático se o modelo estiver deprecado/indisponível
# - Mantém saída em JSON (response_format=json_object)
# - Loga de forma clara qual modelo foi selecionado
# ============================================================

import os
import json
import logging
import requests
from typing import List, Optional

logger = logging.getLogger(__name__)

GROQ_API_KEY_NF = os.getenv("GROQ_API_KEY_NF", os.getenv("GROQ_API_KEY"))
# Você pode passar uma lista no .env separada por vírgulas para forçar ordem:
# Ex.: GROQ_MODEL_NF="llama-3.3-70b-versatile,llama-3.3-8b-instant,gemma2-9b-it"
GROQ_MODEL_NF_RAW = os.getenv("GROQ_MODEL_NF", "").strip()
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

# Cache do modelo selecionado para esta execução (evita re-tentar a cada chamada)
_SELECTED_MODEL: Optional[str] = None


def _candidate_models() -> List[str]:
    """
    Prioriza a lista definida em GROQ_MODEL_NF (se múltiplos, separados por vírgula).
    Se vazio, usa uma ordem padrão estável e atual (Out/2025).
    """
    # Se o usuário definiu uma lista no .env, respeitar a ordem
    if GROQ_MODEL_NF_RAW:
        parts = [m.strip() for m in GROQ_MODEL_NF_RAW.split(",") if m.strip()]
        if parts:
            return parts

    # Ordem padrão (atualizada): prioriza 3.3-70B, depois 3.3-8B e por fim Gemma
    return [
        "llama-3.3-70b-versatile",
        "llama-3.3-8b-instant",
        "gemma2-9b-it",
    ]


def _post_chat_completion(model: str, prompt: str) -> dict:
    if not GROQ_API_KEY_NF:
        raise RuntimeError("GROQ_API_KEY_NF não configurada no ambiente.")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY_NF}",
        "Content-Type": "application/json",
    }

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é um especialista em leitura de notas fiscais brasileiras (NF-e), "
                    "com foco em produtos controlados: armas, munições e acessórios. "
                    "Retorne SEMPRE um JSON válido."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        # Força a saída JSON (padrão Groq compatível com OpenAI)
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
    }

    logger.info(f"[LLM_NF] Chamando modelo '{model}' (prompt chars: {len(prompt)})")
    resp = requests.post(GROQ_ENDPOINT, headers=headers, json=body, timeout=120)

    # Caso de sucesso (200)
    if resp.status_code == 200:
        return resp.json()

    # Tenta ler payload de erro para tomar decisão de fallback
    try:
        err = resp.json()
    except Exception:
        err = {"error": {"message": resp.text or "Erro desconhecido"}}

    code = (err.get("error") or {}).get("code") or ""
    message = (err.get("error") or {}).get("message") or ""
    logger.warning(f"[LLM_NF] Erro {resp.status_code} no modelo '{model}': {message}")

    # Sinais claros para tentar fallback de modelo:
    # - model_decommissioned
    # - model_not_found
    # - invalid_request_error com texto indicando deprecado
    decommission_signals = ["model_decommissioned", "model_not_found"]
    if resp.status_code in (400, 404) and (
        any(s in code for s in decommission_signals)
        or "decommissioned" in message.lower()
        or "does not exist" in message.lower()
        or "not supported" in message.lower()
    ):
        raise ModelUnavailableError(message)

    # 413/429/402: limites/contexto/tier — repassar para camada acima
    if resp.status_code in (402, 413, 429):
        raise RuntimeError(f"Limite/Contexto: {resp.status_code} - {message}")

    # Demais erros — repassar
    raise RuntimeError(f"Erro na chamada LLM: {resp.status_code} - {message}")


class ModelUnavailableError(Exception):
    """Erro para indicar que o modelo está indisponível/deprecado e devemos tentar fallback."""


def _select_model_with_fallback(prompt: str) -> str:
    """
    Tenta os modelos candidatos em ordem e retorna o primeiro que responder sem erro
    de deprecation/not_found. Cacheia o modelo escolhido em _SELECTED_MODEL.
    """
    global _SELECTED_MODEL
    if _SELECTED_MODEL:
        return _SELECTED_MODEL

    last_error = None
    for model in _candidate_models():
        try:
            # Faz uma requisição curta de verificação (barata) com o próprio prompt.
            data = _post_chat_completion(model, prompt)
            # Se chegou aqui com 200, apenas valida o shape mínimo
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            # Não vamos parsear aqui — a função principal fará isso.
            _SELECTED_MODEL = model
            logger.info(f"[LLM_NF] Modelo selecionado (cache): {model}")
            return _SELECTED_MODEL
        except ModelUnavailableError as e:
            logger.warning(f"[LLM_NF] Modelo indisponível '{model}', tentando próximo... ({e})")
            last_error = e
            continue
        except Exception as e:
            # Para erros de limite/timeout/etc., não trocar de modelo automaticamente.
            last_error = e
            logger.warning(f"[LLM_NF] Falha com '{model}' (sem sinal de deprecation): {e}")
            # Ainda assim, tentamos o próximo modelo — pode ser quota/tier temporário.
            continue

    # Se nenhum candidato funcionou, propaga o último erro significativo
    raise RuntimeError(f"Nenhum modelo Groq disponível/aceito. Último erro: {last_error}")


def call_nf_llm(prompt: str):
    """
    API pública usada pelo parser inteligente (utils_llm.py).
    - Resolve modelo com fallback
    - Retorna dicionário (JSON) vindo do LLM
    """
    # Seleciona (ou reaproveita) o modelo
    model = _select_model_with_fallback(prompt)

    # Chamada efetiva agora que já sabemos um modelo válido
    data = _post_chat_completion(model, prompt)

    # Extrai conteúdo
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")

    # Tenta decodificar JSON; se não for possível, devolve texto bruto
    try:
        return json.loads(content) if content else {}
    except json.JSONDecodeError:
        logger.warning("[LLM_NF] Resposta não estava em JSON puro. Retornando texto bruto.")
        return {"raw": content}