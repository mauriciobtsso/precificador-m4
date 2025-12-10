# workers/worker_certidoes.py
import sys
import os
import redis
from rq import Worker, Queue, Connection

# Adiciona a raiz do projeto ao PYTHONPATH
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app

listen = ["m4_certidoes"]

if __name__ == "__main__":
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    try:
        conn = redis.from_url(redis_url)
        # Tenta conectar para falhar rápido se não houver Redis
        conn.ping()
    except Exception as e:
        print(f"[WORKER ERROR] Não foi possível conectar ao Redis: {e}")
        sys.exit(1)

    app = create_app()
    
    # O contexto da aplicação é obrigatório para acessar BD e Models
    with app.app_context():
        print(f" [WORKER] M4 Certidões iniciado.")
        print(f" [WORKER] Escutando filas: {listen}")
        print(f" [WORKER] Redis: {redis_url}")

        with Connection(conn):
            worker = Worker(list(map(Queue, listen)))
            worker.work()