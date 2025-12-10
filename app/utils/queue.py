# app/utils/queue.py

import os
import redis
from rq import Queue

# URL do Redis:
# Tenta pegar do ambiente, senão usa localhost
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Inicializa variáveis como None para o caso de falha
redis_conn = None
fila_certidoes = None

try:
    # Tenta criar a conexão
    redis_conn = redis.from_url(REDIS_URL)
    
    # Faz um PING rápido para garantir que o servidor existe e está rodando
    redis_conn.ping()
    
    # Se passou do ping, cria a fila
    fila_certidoes = Queue("m4_certidoes", connection=redis_conn)
    
    print(f"[QUEUE] Conectado ao Redis com sucesso: {REDIS_URL}")

except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
    print(f"[QUEUE] AVISO: Não foi possível conectar ao Redis em {REDIS_URL}.")
    print("[QUEUE] O sistema rodará em modo SÍNCRONO (sem fila) para Certidões.")
    redis_conn = None
    fila_certidoes = None

except Exception as e:
    print(f"[QUEUE] Erro inesperado ao configurar Redis: {e}")
    redis_conn = None
    fila_certidoes = None