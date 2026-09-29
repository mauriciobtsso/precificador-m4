# app/carrinho/logic.py
import requests
from decimal import Decimal


class CartOrchestrator:
    def __init__(self, carrinho):
        self.carrinho = carrinho

    def calcular_frete(self, cep_destino):
        """Estimativa legada usada apenas pelos fluxos que ainda dependem dela."""
        if not cep_destino:
            return Decimal(0)
        return Decimal("25.00")

    def preparar_checkout_transparente(self, gateway="mercadopago"):
        return {
            "items": [
                {
                    "title": item.produto.nome,
                    "quantity": item.quantidade,
                    "unit_price": float(item.preco_unitario_no_momento),
                }
                for item in self.carrinho.items
            ],
            "total": float(self.carrinho.total_avista),
        }


class PagarmeAPIError(Exception):
    """Erro sanitizado da API; nunca guarda/expõe chave ou payload sensível."""

    def __init__(self, message, status_code=None, ambiguous=False):
        super().__init__(message)
        self.status_code = status_code
        self.ambiguous = ambiguous


class PagarmeOrchestrator:
    BASE_URL = "https://api.pagar.me/core/v5"

    def __init__(self, api_key, http=requests, timeout=20):
        self.api_key = str(api_key or "").strip()
        self.http = http
        self.timeout = timeout

    def _request(self, method, path, **kwargs):
        if not self.api_key:
            raise PagarmeAPIError("A chave secreta do Pagar.me não está configurada.")
        try:
            response = self.http.request(
                method,
                f"{self.BASE_URL}{path}",
                auth=(self.api_key, ""),
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise PagarmeAPIError(
                "Não foi possível confirmar a resposta do Pagar.me.", ambiguous=True
            ) from exc

        try:
            data = response.json()
        except (ValueError, AttributeError):
            data = {}

        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code < 200 or status_code >= 300:
            raise PagarmeAPIError(
                f"O Pagar.me recusou a operação (HTTP {status_code}).",
                status_code=status_code,
                ambiguous=status_code >= 500,
            )
        if not isinstance(data, dict):
            raise PagarmeAPIError("O Pagar.me retornou uma resposta inválida.", ambiguous=True)
        return data

    def criar_pedido(self, payload):
        return self._request("POST", "/orders", json=payload)

    def obter_pedido(self, pagarme_id):
        return self._request("GET", f"/orders/{str(pagarme_id)}")
