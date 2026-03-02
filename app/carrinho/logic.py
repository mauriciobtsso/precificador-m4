# app/carrinho/logic.py
import requests
import json
from decimal import Decimal

class CartOrchestrator:
    def __init__(self, carrinho):
        self.carrinho = carrinho

    def calcular_frete(self, cep_destino):
        """
        Aqui faremos a chamada para API (Kangu/Melhor Envio).
        Por enquanto, retornamos um mock (simulação).
        """
        # Exemplo: logic para chamar Kangu ficaria aqui
        if not cep_destino:
            return Decimal(0)
        return Decimal(25.00) # Simulação de frete fixo

    def preparar_checkout_transparente(self, gateway="mercadopago"):
        """
        Prepara os dados para o Checkout Transparente.
        Retorna os tokens/scripts necessários para o frontend.
        """
        dados_pedido = {
            "items": [
                {
                    "title": item.produto.nome,
                    "quantity": item.quantidade,
                    "unit_price": float(item.preco_unitario_no_momento)
                } for item in self.carrinho.items
            ],
            "total": float(self.carrinho.total_avista)
        }
        return dados_pedido

class PagarmeOrchestrator:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.pagar.me/core/v5"

    def preparar_pedido_transparente(self, carrinho, dados_cliente, frete_selecionado):
        """
        Gera a estrutura JSON para enviar ao Pagar.me
        """
        items = []
        for item in carrinho.items:
            items.append({
                "amount": int(item.preco_unitario_no_momento * 100), # Pagar.me usa centavos (ex: R$ 10,00 = 1000)
                "description": item.produto.nome,
                "quantity": item.quantidade,
                "code": item.produto.codigo
            })

        payload = {
            "items": items,
            "customer": {
                "name": dados_cliente['nome'],
                "email": dados_cliente['email'],
                "document": dados_cliente['documento'].replace('.', '').replace('-', ''),
                "type": "individual",
                "phones": {
                    "mobile_phone": {
                        "country_code": "55",
                        "area_code": dados_cliente['ddd'],
                        "number": dados_cliente['telefone']
                    }
                }
            },
            "payments": [
                {
                    "payment_method": dados_cliente['metodo'], # 'credit_card' ou 'pix'
                    # Aqui entra o 'card_token' gerado pelo JS no frontend
                }
            ]
        }
        return payload

