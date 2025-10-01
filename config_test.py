# config_test.py
import os

class TestConfig:
    TESTING = True
    DEBUG = False
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_TEST_URI", "sqlite:///:memory:")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False  # desliga CSRF nos testes
