import requests

class MelhorEnvioService:
    def __init__(self, token):
        self.token = token
        self.url = "https://www.melhorenvio.com.br/api/v2/me/shipment/calculate"
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "M4 Tatica (contato@m4tatica.com.br)"
        }

    def calcular_frete(self, cep_origem, cep_destino, itens_carrinho):
        """
        itens_carrinho deve ser uma lista de objetos do tipo CarrinhoItem
        """
        products = []
        for item in itens_carrinho:
            products.append({
                "id": str(item.produto.id),
                "width": float(item.produto.largura or 11), # Padrão mínimo se vazio
                "height": float(item.produto.altura or 2),
                "length": float(item.produto.comprimento or 16),
                "weight": float(item.produto.peso or 0.3),
                "insurance_value": float(item.produto.preco_unitario_no_momento),
                "quantity": item.quantidade
            })

        payload = {
            "from": {"postal_code": cep_origem},
            "to": {"postal_code": cep_destino},
            "products": products,
            "options": {
                "receipt": False,
                "own_hand": False
            }
        }

        try:
            response = requests.post(self.url, json=payload, headers=self.headers)
            if response.status_code == 200:
                # Filtrar apenas as transportadoras ativas (ex: SEDEX, PAC, Jadlog)
                return [servico for servico in response.json() if not servico.get('error')]
            return None
        except Exception as e:
            print(f"Erro Melhor Envio: {e}")
            return None