import sys
import os

# Adiciona a raiz do projeto ao PYTHONPATH
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from rq import Connection, Worker
from redis import Redis
from app import create_app
from app.utils.queue import fila_certidoes


# ============================================================
# Worker compatível com Windows (sem SIGALRM)
# ============================================================

listen = ['m4_certidoes']

app = create_app()
app.app_context().push()

redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
conn = Redis.from_url(redis_url)

if __name__ == '__main__':
    with Connection(conn):
        worker = Worker(
            listen, 
            exception_handlers=[],
            disable_sig_handlers=True,     # ← ESSENCIAL
            disable_default_exception_handler=True,
            job_monitoring_interval=5,     # evita watchdog com SIGALRM
        )
        worker.work(with_scheduler=True)
