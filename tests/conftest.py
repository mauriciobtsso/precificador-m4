import pytest
from app import create_app, db
from app.config_test import TestConfig

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
