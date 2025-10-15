# ===========================
# ALERTAS - AGENDADOR DIÁRIO (Sprint 4.3 - v4 Estável)
# ===========================

from datetime import datetime
import time
import traceback
from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app

from app.extensions import db
from app.utils.alertas import gerar_alertas_gerais
from app.alertas.notificacoes import enviar_notificacao


# -----------------------------------------------------
# 🔹 Função principal: verificar_alertas_diarios()
# -----------------------------------------------------
def verificar_alertas_diarios(app=None):
    """
    Executa verificação automática de alertas e registra notificações.
    Pode ser executada manualmente ou via agendador APScheduler.
    """

    ctx = None
    if app:
        try:
            ctx = app.app_context()
            ctx.push()
        except Exception:
            pass  # já dentro do contexto

    inicio = datetime.now()
    print(f"[{inicio:%Y-%m-%d %H:%M:%S}] 🔄 Iniciando verificação diária de alertas...")

    try:
        total_novos = 0
        inicio_exec = time.time()

        # 1️⃣ Gera alertas consolidados do sistema
        resultado = gerar_alertas_gerais()

        # ✅ Suporte a retorno paginado (dict com "data")
        if isinstance(resultado, dict) and "data" in resultado:
            alertas = resultado["data"]
        else:
            alertas = resultado or []

        print(f"   ➜ {len(alertas)} alertas encontrados para análise.")

        # 2️⃣ Processa cada alerta individualmente
        for alerta in alertas:
            try:
                registro = enviar_notificacao(alerta, meio="sistema")
                if registro:
                    total_novos += 1
            except Exception as e:
                print(f"   ⚠️ Erro ao registrar alerta: {e}")
                traceback.print_exc()

        # 3️⃣ Finaliza e exibe resumo
        fim = datetime.now()
        duracao = time.time() - inicio_exec
        print(f"[{fim:%Y-%m-%d %H:%M:%S}] ✅ {total_novos} novas notificações registradas ({duracao:.1f}s)")

    except Exception as e:
        print("❌ Erro na verificação diária de alertas:")
        traceback.print_exc()

    finally:
        if ctx:
            ctx.pop()


# -----------------------------------------------------
# 🔹 Função: iniciar_scheduler()
# -----------------------------------------------------
def iniciar_scheduler(app):
    """
    Configura e inicia o APScheduler integrado ao Flask.
    Executa a verificação diariamente às 06:00 (horário do servidor).
    """

    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")

    # Remove tarefas antigas duplicadas
    for job in scheduler.get_jobs():
        scheduler.remove_job(job.id)

    # Adiciona a tarefa diária
    scheduler.add_job(
        func=lambda: verificar_alertas_diarios(app),
        trigger="cron",
        hour=6,
        minute=0,
        id="verificacao_alertas_diarios",
        replace_existing=True,
    )

    scheduler.start()
    print("Agendador de alertas iniciado (executa diariamente às 06:00).")
    return scheduler


# -----------------------------------------------------
# 🔹 Execução manual (CLI)
# -----------------------------------------------------
if __name__ == "__main__":
    """
    Permite execução manual via terminal:
    > py -m app.alertas.tasks
    """
    from app import create_app

    app = create_app()
    with app.app_context():
        print("⚙️ Executando verificação manual de alertas...")
        verificar_alertas_diarios(app)
