# ===========================
# ALERTAS - AGENDADOR DIÁRIO (Sprint 4.3 - v4 Estável)
# + Ajuste Automático de Sequências (Sprint 6G)
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


# ============================================================
# 🔹 Função auxiliar: corrigir_todas_as_sequencias()
# ============================================================
from sqlalchemy import text

TABELAS_SEQUENCIAS = [
    "produtos",
    "categoria_produto",
    "marca_produto",
    "tipo_produto",
    "calibre_produto",
    "funcionamento_produto",
]

def corrigir_todas_as_sequencias():
    """
    Corrige automaticamente as sequências (auto-increment) das tabelas
    relacionadas a produtos e configurações, prevenindo erros de
    'duplicate key value violates unique constraint'.
    Executada diariamente às 03:00 via APScheduler.
    """
    try:
        from app import db
        total_corrigidas = 0
        falhas = []

        for tabela in TABELAS_SEQUENCIAS:
            try:
                sql = text(f"""
                    SELECT setval(
                        pg_get_serial_sequence('{tabela}', 'id'),
                        COALESCE((SELECT MAX(id) FROM {tabela}), 1),
                        TRUE
                    );
                """)
                db.session.execute(sql)
                db.session.commit()
                current_app.logger.info(f"[AUTOSEQ] Sequência corrigida para '{tabela}' ✅")
                total_corrigidas += 1
            except Exception as e:
                db.session.rollback()
                falhas.append((tabela, str(e)))
                current_app.logger.error(f"[AUTOSEQ] Falha ao corrigir sequência de '{tabela}': {e}")

        resumo = f"{total_corrigidas} sequência(s) corrigida(s) às {datetime.now():%d/%m/%Y %H:%M:%S}"
        if falhas:
            resumo += f" — Falhas em: {', '.join(t for t, _ in falhas)}"
        current_app.logger.info(f"[AUTOSEQ] {resumo}")

    except Exception as e:
        current_app.logger.error(f"[AUTOSEQ] Erro geral no ajuste automático de sequências: {e}")
        traceback.print_exc()


# -----------------------------------------------------
# 🔹 Função: iniciar_scheduler()
# -----------------------------------------------------
def iniciar_scheduler(app):
    """
    Configura e inicia o APScheduler integrado ao Flask.
    Executa:
      • Verificação de alertas às 06:00
      • Ajuste de sequências às 03:00
    """

    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")

    # Remove tarefas antigas duplicadas
    for job in scheduler.get_jobs():
        scheduler.remove_job(job.id)

    # === 1️⃣ Verificação de alertas diários ===
    scheduler.add_job(
        func=lambda: verificar_alertas_diarios(app),
        trigger="cron",
        hour=6,
        minute=0,
        id="verificacao_alertas_diarios",
        replace_existing=True,
    )

    # === 2️⃣ Ajuste automático de sequências ===
    scheduler.add_job(
        func=corrigir_todas_as_sequencias,
        trigger="cron",
        hour=3,
        minute=0,
        id="ajuste_sequencias_diario",
        replace_existing=True,
    )

    scheduler.start()
    print("🕒 Agendador iniciado: alertas (06:00) e ajuste de sequências (03:00).")
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

        print("⚙️ Executando ajuste manual de sequências...")
        corrigir_todas_as_sequencias()
