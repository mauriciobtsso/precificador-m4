# app/certidoes/__init__.py

# Mantém este módulo bem simples, só expondo o blueprint correto.

from .routes.main import certidoes_bp

__all__ = ["certidoes_bp"]
