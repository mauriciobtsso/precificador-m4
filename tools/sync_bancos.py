"""
====================================================
SCRIPT: Sync Bancos Neon ↔️ Locaweb (Precificador M4)
Autor: Mauricio Batista de Sousa
====================================================

Permite sincronizar dados entre os bancos Neon e Locaweb
com backup local e log detalhado.
"""

import os
import sys
import subprocess
from datetime import datetime

# =====================================
# CONFIGURAÇÕES DE CONEXÃO
# =====================================
NEON_URI = (
    "postgresql://neondb_owner:npg_qXEJL5vYs7Zz"
    "@ep-young-cake-ad2mlkly-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"
)
LOCAWEB_URI = (
    "postgresql://m4_app:M4tatica@2021@m4_app.postgresql.dbaas.com.br/m4_app"
)

# =====================================
# LOGGING
# =====================================
LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "sync_bancos.log")

def registrar_log(msg):
    """Escreve mensagens em logs/sync_bancos.log com data/hora."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")

def log(msg, tipo="info"):
    """Exibe mensagem colorida e grava em log."""
    cores = {
        "info": "\033[94m",     # azul
        "sucesso": "\033[92m",  # verde
        "erro": "\033[91m",     # vermelho
        "aviso": "\033[93m",    # amarelo
    }
    cor = cores.get(tipo, "")
    print(f"{cor}{msg}\033[0m")
    registrar_log(msg)

# =====================================
# FUNÇÕES AUXILIARES
# =====================================
def executar_comando(comando, erro_msg):
    """Executa comandos de terminal com tratamento de erro."""
    try:
        subprocess.run(comando, check=True)
    except subprocess.CalledProcessError as e:
        log(f"❌ {erro_msg}", "erro")
        log(str(e), "erro")
        registrar_log("ERRO DETALHADO: " + str(e))
        sys.exit(1)


def verificar_pg_tools():
    """Verifica se pg_dump e psql estão instalados e acessíveis."""
    for tool in ["pg_dump", "psql"]:
        if not any(
            os.access(os.path.join(path, tool), os.X_OK)
            for path in os.environ["PATH"].split(os.pathsep)
        ):
            log(f"⚠️ Ferramenta '{tool}' não encontrada no sistema PATH.", "erro")
            log("💡 Instale o PostgreSQL Client Tools para usar este script.", "erro")
            sys.exit(1)


def sincronizar_bancos(origem, destino, nome_origem, nome_destino):
    """Executa a sincronização com backup e registro detalhado."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    backup_dir = os.path.join(os.getcwd(), "backups")
    os.makedirs(backup_dir, exist_ok=True)

    backup_file = os.path.join(
        backup_dir, f"{timestamp}_{nome_origem}_para_{nome_destino}.sql"
    )

    log(f"\n💾 Iniciando sincronização: {nome_origem.upper()} → {nome_destino.upper()}")
    log(f"📂 Backup será salvo em: {backup_file}", "aviso")

    # 1️⃣ Backup do banco de origem
    log(f"🔸 Gerando backup do banco {nome_origem}...", "info")
    registrar_log(f"Iniciando backup de {nome_origem}")
    executar_comando(
        ["pg_dump", origem, "-f", backup_file],
        f"Erro ao gerar backup do banco {nome_origem}.",
    )

    # 2️⃣ Restauração no banco de destino
    log(f"🔸 Restaurando backup no banco {nome_destino}...", "info")
    registrar_log(f"Restaurando backup no destino {nome_destino}")
    executar_comando(
        ["psql", destino, "-f", backup_file],
        f"Erro ao restaurar backup no banco {nome_destino}.",
    )

    log(f"\n✅ Sincronização concluída com sucesso ({nome_origem} → {nome_destino})!", "sucesso")
    log(f"🗂 Backup local: {backup_file}", "aviso")
    registrar_log(f"Sincronização finalizada: {nome_origem} → {nome_destino}")


# =====================================
# PONTO DE ENTRADA
# =====================================
if __name__ == "__main__":
    verificar_pg_tools()

    if len(sys.argv) != 2:
        log("Uso correto:", "aviso")
        print("  python tools/sync_bancos.py --neon-para-locaweb")
        print("  python tools/sync_bancos.py --locaweb-para-neon")
        sys.exit(1)

    opcao = sys.argv[1].lower()

    registrar_log(f"===== NOVA EXECUÇÃO ({opcao}) =====")

    if opcao == "--neon-para-locaweb":
        sincronizar_bancos(NEON_URI, LOCAWEB_URI, "neon", "locaweb")
    elif opcao == "--locaweb-para-neon":
        sincronizar_bancos(LOCAWEB_URI, NEON_URI, "locaweb", "neon")
    else:
        log("❌ Opção inválida.", "erro")
        print("Use --neon-para-locaweb ou --locaweb-para-neon")
        sys.exit(1)
