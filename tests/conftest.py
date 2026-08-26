import os

import pytest

os.environ.setdefault("SECRET_KEY", "test-only-secret-key")
os.environ.setdefault("GROQ_API_KEY", "test-only-groq-key")

from app.config_test import TestConfig
from config import Config

# A factory lê Config antes de inicializar Flask-SQLAlchemy. O fixture antigo
# aplicava TestConfig depois dessa inicialização, deixando o banco sem URI.
Config.SQLALCHEMY_DATABASE_URI = TestConfig.SQLALCHEMY_DATABASE_URI
Config.SQLALCHEMY_ENGINE_OPTIONS = {}

from app import create_app, db


@pytest.fixture(scope="session")
def app():
    """Cria uma instância da aplicação só para os testes."""
    app = create_app()
    app.config.from_object(TestConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    """Cliente de teste para simular requests."""
    return app.test_client()
