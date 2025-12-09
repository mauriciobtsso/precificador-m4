# app/utils/queue.py

import os
from redis import Redis
from rq import Queue


def get_redis_connection():
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return Redis.from_url(url)


# Fila principal das certidões
redis_conn = get_redis_connection()
fila_certidoes = Queue("m4_certidoes", connection=redis_conn)
