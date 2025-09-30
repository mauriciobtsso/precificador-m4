import pandas as pd
from datetime import datetime
import sys
import os

# Garante que a pasta raiz do projeto esteja no sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.clientes.models import Cliente, EnderecoCliente, ContatoCliente


def safe_date(value):
    """Converte valor em datetime.date ou None"""
    if pd.isna(value) or value in ("", None):
        return None
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def safe_str(value):
    """Converte NaN em None"""
    if pd.isna(value) or value in ("", None):
        return None
    return str(value).strip()


def importar_clientes(caminho_excel):
    app = create_app()
    with app.app_context():
        df = pd.read_excel(caminho_excel)

        for _, row in df.iterrows():
            documento = safe_str(row.get("Documento (CPF / CNPJ)"))
            if not documento:
                print("⚠️ Linha ignorada: documento vazio")
                continue

            # Verifica se já existe cliente com esse documento
            cliente = Cliente.query.filter_by(documento=documento).first()

            if cliente:
                print(f"🔄 Atualizando cliente existente: {cliente.nome}")
            else:
                cliente = Cliente(documento=documento)
                db.session.add(cliente)
                print(f"➕ Criando novo cliente: {safe_str(row.get('Nome'))}")

            # --- Atualiza campos principais ---
            cliente.nome = safe_str(row.get("Nome")) or cliente.nome
            cliente.razao_social = safe_str(row.get("Razão Social")) or cliente.razao_social
            cliente.rg = safe_str(row.get("RG")) or cliente.rg
            cliente.rg_emissor = safe_str(row.get("RG emissor")) or cliente.rg_emissor
            cliente.cr = safe_str(row.get("CR")) or cliente.cr
            cliente.cr_emissor = safe_str(row.get("CR Emissor")) or cliente.cr_emissor
            cliente.data_validade_cr = safe_date(row.get("CR Validade")) or cliente.data_validade_cr
            cliente.sigma = safe_str(row.get("SIGMA")) or cliente.sigma
            cliente.sinarm = safe_str(row.get("SINARM")) or cliente.sinarm
            cliente.sexo = safe_str(row.get("Sexo")) or cliente.sexo
            cliente.profissao = safe_str(row.get("Profissão")) or cliente.profissao
            cliente.estado_civil = safe_str(row.get("Estado Civil")) or cliente.estado_civil
            cliente.data_nascimento = safe_date(row.get("Data de Nascimento")) or cliente.data_nascimento
            cliente.nome_pai = safe_str(row.get("Pai")) or cliente.nome_pai
            cliente.nome_mae = safe_str(row.get("Mãe")) or cliente.nome_mae
            cliente.nacionalidade = safe_str(row.get("Nacionalidade")) or cliente.nacionalidade
            cliente.inscricao_estadual = safe_str(row.get("Inscrição Estadual")) or cliente.inscricao_estadual
            cliente.inscricao_municipal = safe_str(row.get("Inscrição Municipal")) or cliente.inscricao_municipal
            cliente.email = safe_str(row.get("E-mail")) or cliente.email
            cliente.telefone = safe_str(row.get("Telefone")) or cliente.telefone
            cliente.celular = safe_str(row.get("Telefone 2")) or cliente.celular

            # Flags
            cliente.cac = bool(row.get("CAC"))
            cliente.filiado = bool(row.get("FILIADO"))
            cliente.policial = bool(row.get("POLICIAL"))
            cliente.bombeiro = bool(row.get("BOMBEIRO"))
            cliente.militar = bool(row.get("MILITAR"))
            cliente.iat = bool(row.get("IAT"))
            cliente.psicologo = bool(row.get("PSICOLOGO"))
            cliente.atirador_n1 = bool(row.get("Atirador - Nível 1"))
            cliente.atirador_n2 = bool(row.get("Atirador - Nível 2"))
            cliente.atirador_n3 = bool(row.get("Atirador - Nível 3"))

            db.session.flush()

            # --- Endereços (substitui os antigos) ---
            EnderecoCliente.query.filter_by(cliente_id=cliente.id).delete()
            for tipo in ["End1", "End2", "End3"]:
                cep = row.get(f"{tipo} - CEP")
                if cep and not pd.isna(cep):
                    endereco = EnderecoCliente(
                        cliente_id=cliente.id,
                        tipo=tipo,
                        cep=safe_str(cep),
                        estado=safe_str(row.get(f"{tipo} - Estado")),
                        cidade=safe_str(row.get(f"{tipo} - Cidade")),
                        bairro=safe_str(row.get(f"{tipo} - Bairro")),
                        rua=safe_str(row.get(f"{tipo} - Rua")),
                        numero=safe_str(row.get(f"{tipo} - Número")),
                        complemento=safe_str(row.get(f"{tipo} - Complemento")),
                    )
                    db.session.add(endereco)

            # --- Contatos extras (substitui os antigos) ---
            ContatoCliente.query.filter_by(cliente_id=cliente.id).delete()
            for col, tipo in [
                ("Telefone 2", "telefone"),
                ("Telefone 3", "telefone"),
                ("E-mail 2", "email"),
            ]:
                valor = row.get(col)
                if valor and not pd.isna(valor):
                    contato = ContatoCliente(
                        cliente_id=cliente.id,
                        tipo=tipo,
                        valor=safe_str(valor),
                    )
                    db.session.add(contato)

        db.session.commit()
        print("🎉 Importação concluída com sucesso!")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        caminho = sys.argv[1]
    else:
        caminho = os.path.join(os.path.dirname(__file__), "..", "pessoas-29092025.xlsx")

    print(f"📂 Importando clientes do arquivo: {caminho}")
    importar_clientes(caminho)
