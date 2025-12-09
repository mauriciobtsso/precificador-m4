# app/certidoes/routes/__init__.py

# Só garante que o pacote "routes" existe e que o main é importável.
from .main import certidoes_bp

__all__ = ["certidoes_bp"]
