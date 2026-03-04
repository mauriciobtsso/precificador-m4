import requests

class MelhorEnvioService:
    def __init__(self, token, sandbox=False):
        self.token = token
        base = "https://sandbox.melhorenvio.com.br" if sandbox else "https://www.melhorenvio.com.br"
        self.url = f"{base}/api/v2/me/shipment/calculate"
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "M4 Tatica (contato@m4tatica.com.br)"
        }

    def calcular_frete(self, cep_origem, cep_destino, itens_carrinho):
        products = []
        for item in itens_carrinho:
            p = item.produto
            products.append({
                "id": str(p.id),
                "width":  float(p.largura     or 11),
                "height": float(p.altura      or 2),
                "length": float(p.comprimento or 16),
                "weight": float(p.peso        or 0.3),
                # preco_unitario_no_momento pertence ao CarrinhoItem, não ao Produto
                "insurance_value": float(item.preco_unitario_no_momento or p.preco_a_vista or 0),
                "quantity": item.quantidade
            })

        payload = {
            "from": {"postal_code": cep_origem},
            "to":   {"postal_code": cep_destino},
            "products": products,
            "options": {"receipt": False, "own_hand": False}
        }

        try:
            response = requests.post(self.url, json=payload, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return [s for s in response.json() if not s.get('error')]
            print(f"Melhor Envio HTTP {response.status_code}: {response.text[:200]}")
            return None
        except Exception as e:
            print(f"Erro Melhor Envio: {e}")
            return None