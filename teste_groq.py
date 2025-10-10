import os
import requests
import json

key = os.environ.get("GROQ_API_KEY")
if not key:
    raise RuntimeError("❌ Variável GROQ_API_KEY não encontrada. Use o comando $env:GROQ_API_KEY=\"SUA_CHAVE\" antes de rodar.")

payload = {
    "model": os.environ.get("GROQ_MODEL", "llama3-70b-8192"),
    "messages": [
        {"role": "system", "content": "Você é um assistente."},
        {"role": "user", "content": "Responda apenas OK."}
    ]
}

r = requests.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={"Authorization": f"Bearer {key}"},
    json=payload,
    timeout=30
)

print("Status:", r.status_code)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
