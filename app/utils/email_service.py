import os
import requests
import logging
from html import escape
from flask import current_app
from app.models import Configuracao


def _moeda_brl(valor):
    """Formata valores monetários para leitura correta no e-mail."""
    try:
        numero = float(valor or 0)
    except (TypeError, ValueError):
        numero = 0.0
    return 'R$ ' + format(numero, ',.2f').replace(',', 'X').replace('.', ',').replace('X', '.')


def enviar_email_brevo(destinatario_email, destinatario_nome, assunto, html_content):
    """
    Envia e-mail utilizando a API v3 da Brevo com suporte ao domínio autenticado m4tatica.com.br.
    """
    api_key = None
    sender_email = "contato@m4tatica.com.br"
    sender_nome = "M4 Tática"

    try:
        cfg_api = Configuracao.query.filter_by(chave='integ_brevo_api_key').first()
        if cfg_api and cfg_api.valor:
            api_key = cfg_api.valor.strip()

        cfg_from = Configuracao.query.filter_by(chave='integ_smtp_from').first()
        if cfg_from and cfg_from.valor:
            sender_email = cfg_from.valor.strip()
    except Exception as e:
        logging.warning(f"[BREVO] Erro ao buscar configs no DB: {e}")

    if not api_key:
        api_key = os.getenv("BREVO_API_KEY")

    if not api_key:
        logging.warning("[BREVO] API Key não configurada. E-mail não enviado.")
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    
    payload = {
        "sender": {"name": sender_nome, "email": sender_email},
        "to": [{"email": destinatario_email, "name": destinatario_nome}],
        "subject": assunto,
        "htmlContent": html_content
    }
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in [201, 200, 202]:
            logging.info(f"[BREVO] E-mail enviado com sucesso para {destinatario_email} via {sender_email}")
            return True
        else:
            logging.error(f"[BREVO] Erro ao enviar e-mail: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logging.error(f"[BREVO] Erro de conexão com API Brevo: {e}")
        return False

def enviar_email_boas_vindas(cliente):
    """E-mail de boas-vindas ao cadastrar na loja."""
    assunto = f"Bem-vindo à M4 Tática, {cliente.nome.split()[0] if cliente.nome else 'Cliente'}!"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #eee; padding: 20px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="color: #c5a059;">M4 TÁTICA</h2>
        </div>
        <p>Olá, <strong>{cliente.nome}</strong>!</p>
        <p>Sua conta foi criada com sucesso em nossa plataforma. Agora você pode acompanhar seus pedidos e gerenciar sua documentação com total segurança.</p>
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 0;"><strong>Seu E-mail de Login:</strong> {cliente.email_login}</p>
        </div>
        <p>Acesse sua conta agora: <a href="https://loja.m4tatica.com.br/login" style="color: #c5a059; font-weight: bold;">Fazer Login</a></p>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #777; text-align: center;">M4 Tática - Assessoria e Comércio de Armas</p>
    </div>
    """
    return enviar_email_brevo(cliente.email_login, cliente.nome, assunto, html)

def enviar_email_novo_pedido(pedido):
    """E-mail enviado ao gerar o pedido (etapa de pagamento)."""
    assunto = f"Pedido #{pedido.id} Realizado - M4 Tática"
    
    itens_html = ""
    for item in pedido.items:
        prod_nome = item.produto.nome if item.produto else 'Produto'
        subtotal_item = float(item.preco_unitario_historico or 0) * int(item.quantidade or 0)
        itens_html += f"<tr><td style='padding: 8px; border-bottom: 1px solid #eee;'>{escape(str(prod_nome))} (x{item.quantidade})</td><td style='padding: 8px; border-bottom: 1px solid #eee; text-align: right;'>{_moeda_brl(subtotal_item)}</td></tr>"

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #eee; padding: 20px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="color: #c5a059;">M4 TÁTICA</h2>
            <p style="font-size: 14px; color: #666;">Pedido #{pedido.id} registrado com sucesso!</p>
        </div>
        <p>Olá, <strong>{escape(str(pedido.nome_cliente or 'Cliente'))}</strong>,</p>
        <p>Recebemos seu pedido e ele já está na etapa de <strong>pagamento</strong>.</p>
        
        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <thead>
                <tr style="background: #f8f9fa;">
                    <th style="padding: 8px; text-align: left;">Item</th>
                    <th style="padding: 8px; text-align: right;">Subtotal</th>
                </tr>
            </thead>
            <tbody>
                {itens_html}
            </tbody>
            <tfoot>
                <tr>
                    <td style="padding: 8px; font-weight: bold;">Frete:</td>
                    <td style="padding: 8px; text-align: right;">{_moeda_brl(pedido.total_frete)}</td>
                </tr>
                <tr style="font-size: 16px; color: #c5a059;">
                    <td style="padding: 8px; font-weight: bold;">Total:</td>
                    <td style="padding: 8px; text-align: right; font-weight: bold;">{_moeda_brl(pedido.total_pedido)}</td>
                </tr>
            </tfoot>
        </table>

        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0; text-align: center;">
            <p style="margin: 0 0 10px 0;">Forma de Pagamento: <strong>{pedido.forma_pagamento.upper()}</strong></p>
            <a href="https://loja.m4tatica.com.br/carrinho/sucesso/{pedido.id}" style="background: #c5a059; color: #fff; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">Ver Detalhes e Pagar</a>
        </div>

        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #777; text-align: center;">M4 Tática - Assessoria e Comércio de Armas</p>
    </div>
    """
    return enviar_email_brevo(pedido.email_cliente, pedido.nome_cliente, assunto, html)

def enviar_email_status_pedido(pedido):
    """E-mail enviado quando o status do pedido é alterado pelo admin."""
    status_label = pedido.status.upper()
    assunto = f"Atualização no Pedido #{pedido.id}: {status_label} - M4 Tática"
    
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #eee; padding: 20px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="color: #c5a059;">M4 TÁTICA</h2>
            <p style="font-size: 14px; color: #666;">Atualização do Pedido #{pedido.id}</p>
        </div>
        <p>Olá, <strong>{escape(str(pedido.nome_cliente or 'Cliente'))}</strong>,</p>
        <p>O status do seu pedido foi atualizado para:</p>
        
        <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
            <span style="font-size: 20px; font-weight: bold; color: #c5a059; text-transform: uppercase;">{pedido.status}</span>
        </div>

        <p>Você pode acompanhar todos os detalhes acessando sua conta: <a href="https://loja.m4tatica.com.br/minha-conta/pedidos" style="color: #c5a059; font-weight: bold;">Meus Pedidos</a></p>

        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #777; text-align: center;">M4 Tática - Assessoria e Comércio de Armas</p>
    </div>
    """
    return enviar_email_brevo(pedido.email_cliente, pedido.nome_cliente, assunto, html)
