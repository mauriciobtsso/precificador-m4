# ============================================================
# MÓDULO: INTEGRAÇÕES — LLM (Groq / OpenAI API compatível)
# ============================================================

import requests
import os
import json

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

def call_llm_model(prompt: str, response_format="json_object"):
    """
    Faz chamada ao modelo Groq (ou OpenAI API compatível).
    Retorna a resposta em JSON (quando possível).
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY não configurada no ambiente.")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é um assistente especializado em leitura e interpretação "
                    "de notas fiscais (armas, munições, acessórios, etc.). "
                    "Responda sempre em JSON válido."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        # 🔹 Compatível com Groq: 'json_object' força saída estruturada
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
    }

    resp = requests.post(GROQ_ENDPOINT, headers=headers, json=body, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Erro na chamada LLM: {resp.status_code} - {resp.text}")

    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"raw": content}
