import os
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"  # banco só na memória
    WTF_CSRF_ENABLED = False  # desabilita CSRF nos forms durante testes
    LOGIN_DISABLED = True     # desabilita login_required
