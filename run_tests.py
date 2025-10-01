import os
import sys
import pytest

def main():
    # Garantir que estamos em ambiente de teste
    os.environ["FLASK_ENV"] = "testing"
    os.environ["TESTING"] = "1"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    # Rodar pytest com opções padrão
    sys.exit(pytest.main(["-v", "--disable-warnings"]))

if __name__ == "__main__":
    main()
