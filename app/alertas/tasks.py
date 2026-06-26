# ===========================================
# ALERTAS - AGENDADOR DIÁRIO
# + Retry robusto para DB (Aiven)
# ===========================================

from datetime import datetime
import time
import traceback
import os

from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app

from sqlalchemy import text
from sqlalchemy import exc as sa_exc

from app.extensions import db
from app.utils.alertas import gerar_alertas_gerais
from app.alertas.notificacoes import enviar_notificacao


# ---------------------------------------------------------
# Helper robusto: executar ação com retry e backoff
# ---------------------------------------------------------
def executar_com_retry(acao, descricao="acao", tentativas=3, pausa_inicial=2):
    """
    Executa a função `acao` com retry em caso de erros de conexão/SSL com o banco.
    - descarta conexões quebradas (db.engine.dispose)
    - faz rollback da sessão atual
    - aplica backoff exponencial entre as tentativas
    """
    pausa = pausa_inicial

    for tentativa in range(1, tentativas + 1):
        try:
            inicio = time.time()
            resultado = acao()
            duracao = time.time() - inicio

            if current_app:
                current_app.logger.info(
                    f"[RETRY] '{descricao}' concluída na tentativa {tentativa}/{tentativas} "
                    f"({duracao:.2f}s)."
                )

            return resultado

        except sa_exc.OperationalError as e:
            if current_app:
                current_app.logger.warning(
                    f"[RETRY] Erro operacional ao executar '{descricao}' "
                    f"(tentativa {tentativa}/{tentativas}): {e}"
                )

            db.session.rollback()
            try:
                db.engine.dispose()
            except Exception:
                pass

            if tentativa >= tentativas:
                if current_app:
                    current_app.logger.error(
                        f"[RETRY] Todas as tentativas falharam para '{descricao}'."
                    )
                raise

            time.sleep(pausa)
            pausa *= 2  # backoff exponencial (2s, 4s, 8s...)

        except Exception as e:
            db.session.rollback()
            if current_app:
                current_app.logger.error(
                    f"[RETRY] Erro não esperado em '{descricao}': {e}",
                    exc_info=True,
                )
            raise


# ---------------------------------------------------------
# Verificação diária de alertas (robusta)
# ---------------------------------------------------------
def verificar_alertas_diarios(app=None):
    """
    Executa verificação automática de alertas e registra notificações.
    Protegida com retry robusto contra falhas temporárias de conexão.
    """
    ctx = None
    if app:
        try:
            ctx = app.app_context()
            ctx.push()
        except Exception:
            pass

    inicio = datetime.now()
    print(f"[{inicio:%Y-%m-%d %H:%M:%S}] 🔄 Iniciando verificação diária de alertas...")
    if current_app:
        current_app.logger.info("🔄 Iniciando verificação diária de alertas...")

    try:
        total_novos = 0
        inicio_exec = time.time()

        resultado = executar_com_retry(
            gerar_alertas_gerais,
            descricao="gerar_alertas_gerais",
            tentativas=3,
            pausa_inicial=3,
        )

        if isinstance(resultado, dict) and "data" in resultado:
            alertas = resultado["data"]
        else:
            alertas = resultado or []

        print(f"   ➜ {len(alertas)} alertas encontrados para análise.")
        if current_app:
            current_app.logger.info(f"[ALERTAS] {len(alertas)} alertas encontrados.")

        for alerta in alertas:
            try:
                registro = enviar_notificacao(alerta, meio="sistema")
                if registro:
                    total_novos += 1
            except Exception as e:
                print(f"   ⚠️ Erro ao registrar alerta: {e}")
                traceback.print_exc()
                if current_app:
                    current_app.logger.error(
                        f"[ALERTAS] Erro ao registrar alerta: {e}",
                        exc_info=True,
                    )

        fim = datetime.now()
        duracao = time.time() - inicio_exec
        print(
            f"[{fim:%Y-%m-%d %H:%M:%S}] ✅ {total_novos} novas notificações "
            f"registradas ({duracao:.1f}s)"
        )
        if current_app:
            current_app.logger.info(
                f"[ALERTAS] ✅ {total_novos} novas notificações registradas "
                f"({duracao:.1f}s)"
            )

    except Exception:
        print("❌ Erro na verificação diária de alertas:")
        traceback.print_exc()
        if current_app:
            current_app.logger.error(
                "❌ Erro na verificação diária de alertas:",
                exc_info=True,
            )

    finally:
        if ctx:
            ctx.pop()


# ---------------------------------------------------------
# Ajuste automático de sequências
# ---------------------------------------------------------
TABELAS_SEQUENCIAS = [
    "produtos",
    "categoria_produto",
    "marca_produto",
    "tipo_produto",
    "calibre_produto",
    "funcionamento_produto",
]


def corrigir_todas_as_sequencias(app=None):
    """
    Corrige automaticamente as sequências (auto-increment) das tabelas
    relacionadas a produtos e configurações.
    """
    ctx = None
    # CIRURGIA A LASER: Adiciona o Contexto da Aplicação
    if app:
        try:
            ctx = app.app_context()
            ctx.push()
        except Exception:
            pass
            
    try:
        from app import db
        total_corrigidas = 0
        falhas = []

        for tabela in TABELAS_SEQUENCIAS:
            def acao_corrigir():
                sql = text(f"""
                    SELECT setval(
                        pg_get_serial_sequence('"{tabela}"', 'id'),
                        COALESCE((SELECT MAX(id) FROM "{tabela}"), 1),
                        TRUE
                    );
                """)
                db.session.execute(sql)
                db.session.commit()

            try:
                executar_com_retry(
                    acao_corrigir,
                    descricao=f"ajuste_sequencia_{tabela}",
                    tentativas=3,
                    pausa_inicial=2,
                )
                msg_ok = f"[AUTOSEQ] Sequência corrigida para '{tabela}' ✅"
                print(msg_ok)
                if current_app:
                    current_app.logger.info(msg_ok)
                total_corrigidas += 1

            except Exception as e:
                db.session.rollback()
                falhas.append((tabela, str(e)))
                msg_err = f"[AUTOSEQ] Falha ao corrigir sequência de '{tabela}': {e}"
                print(msg_err)
                if current_app:
                    current_app.logger.error(msg_err, exc_info=True)

        resumo = (f"{total_corrigidas} sequência(s) corrigida(s) às "
                  f"{datetime.now():%d/%m/%Y %H:%M:%S}")
        if falhas:
            resumo += f" — Falhas em: {', '.join(t for t, _ in falhas)}"

        print(f"[AUTOSEQ] {resumo}")
        if current_app:
            current_app.logger.info(f"[AUTOSEQ] {resumo}")

    except Exception as e:
        msg = f"[AUTOSEQ] Erro geral no ajuste automático de sequências: {e}"
        print(msg)
        traceback.print_exc()
        if current_app:
            current_app.logger.error(msg, exc_info=True)
            
    finally:
        if ctx:
            ctx.pop()


# ---------------------------------------------------------
# Iniciar Scheduler (CIRURGIA A LASER: KEEP-ALIVE REMOVIDO)
# ---------------------------------------------------------
def iniciar_scheduler(app):
    """
    Configura e inicia o APScheduler integrado ao Flask.
    """
    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")

    for job in scheduler.get_jobs():
        scheduler.remove_job(job.id)

    scheduler.add_job(
        func=lambda: verificar_alertas_diarios(app),
        trigger="cron",
        hour=6,
        minute=0,
        id="verificacao_alertas_diarios",
        replace_existing=True,
    )

    scheduler.add_job(
        func=lambda: corrigir_todas_as_sequencias(app), # Passa a variável 'app' aqui
        trigger="cron",
        hour=3,
        minute=0,
        id="ajuste_sequencias_diario",
        replace_existing=True,
    )

    scheduler.start()
    print("Agendador iniciado com sucesso: alertas (06:00) e ajuste de sequências (03:00).")
    if current_app:
        current_app.logger.info("Scheduler iniciado: alertas (06:00) e auto-sequência (03:00).")
    return scheduler


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    with app.app_context():
        print("⚙️ Executando verificação manual de alertas...")
        verificar_alertas_diarios(app)

        print("⚙️ Executando ajuste manual de sequências...")
        corrigir_todas_as_sequencias()