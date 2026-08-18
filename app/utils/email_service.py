import os
import requests
import logging
from flask import current_app

def enviar_email_brevo(destinatario_email, destinatario_nome, assunto, html_content):
    """
    Envia e-mail utilizando a API v3 da Brevo (antigo Sendinblue).
    """
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("BREVO_SENDER_EMAIL", "contato@m4tatica.com.br")
    sender_nome = os.getenv("BREVO_SENDER_NAME", "M4 Tática")

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
            logging.info(f"[BREVO] E-mail enviado com sucesso para {destinatario_email}")
            return True
        else:
            logging.error(f"[BREVO] Erro ao enviar e-mail: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logging.error(f"[BREVO] Erro de conexão com API Brevo: {e}")
        return False

def enviar_email_boas_vindas(cliente):
    """Helper para e-mail de boas-vindas."""
    assunto = f"Bem-vindo à M4 Tática, {cliente.nome.split()[0]}!"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #eee; padding: 20px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="color: #c5a059;">M4 TÁTICA</h2>
        </div>
        <p>Olá, <strong>{cliente.nome}</strong>!</p>
        <p>Sua conta foi criada com sucesso em nossa plataforma. Agora você pode acompanhar seus pedidos e gerenciar sua documentação de forma simplificada.</p>
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 0;"><strong>Seu Login:</strong> {cliente.email_login}</p>
        </div>
        <p>Acesse sua conta agora: <a href="https://loja.m4tatica.com.br/login" style="color: #c5a059; font-weight: bold;">Fazer Login</a></p>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #777; text-align: center;">M4 Tática - Assessoria e Comércio de Armas</p>
    </div>
    """
    return enviar_email_brevo(cliente.email_login, cliente.nome, assunto, html)
