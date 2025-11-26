import pandas as pd
from datetime import datetime
import sys
import os

# Garante que a pasta raiz do projeto esteja no sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.clientes.models import Cliente, EnderecoCliente, ContatoCliente
from app.tasks.ajuste_sequencias import corrigir_todas_as_sequencias  # <--- IMPORTADO

def safe_date(value):
    """Converte valor em datetime.date ou None"""
    if pd.isna(value) or value in ("", None):
        return None
    try:
        # dayfirst=True para garantir que DD/MM/YYYY seja lido corretamente
        return pd.to_datetime(value, dayfirst=True).date()
    except Exception:
        return None


def safe_str(value):
    """Converte NaN em None e garante string limpa"""
    if pd.isna(value) or value in ("", None):
        return None
    s = str(value).strip()
    return s if s else None


def importar_clientes(caminho_excel):
    app = create_app()
    with app.app_context():
        
        # --- CORREÇÃO PRÉVIA DAS SEQUÊNCIAS ---
        print("🔧 Executando ajuste de sequências do banco de dados...")
        corrigir_todas_as_sequencias()
        print("---")

        # Lê o arquivo (suporta .xlsx e .csv)
        if caminho_excel.endswith('.csv'):
            df = pd.read_csv(caminho_excel)
        else:
            df = pd.read_excel(caminho_excel)

        total_importados = 0

        for _, row in df.iterrows():
            documento = safe_str(row.get("Documento (CPF / CNPJ)"))
            nome = safe_str(row.get("Nome"))
            
            if not documento and not nome:
                continue

            # Tenta buscar pelo documento, se não tiver, busca pelo nome exato
            cliente = None
            if documento:
                cliente = Cliente.query.filter_by(documento=documento).first()
            
            if not cliente and nome:
                 cliente = Cliente.query.filter_by(nome=nome).first()

            if cliente:
                print(f"🔄 Atualizando: {cliente.nome}")
            else:
                cliente = Cliente()
                db.session.add(cliente)
                print(f"➕ Criando: {nome}")

            # --- Atualiza campos principais (Tabela Cliente) ---
            cliente.nome = nome or cliente.nome
            cliente.documento = documento or cliente.documento
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
            
            # Flags booleanas
            def get_bool(col):
                val = row.get(col)
                if pd.isna(val): return None
                return bool(val)

            cliente.cac = get_bool("CAC") if get_bool("CAC") is not None else cliente.cac
            cliente.filiado = get_bool("FILIADO") if get_bool("FILIADO") is not None else cliente.filiado
            cliente.policial = get_bool("POLICIAL") if get_bool("POLICIAL") is not None else cliente.policial
            cliente.bombeiro = get_bool("BOMBEIRO") if get_bool("BOMBEIRO") is not None else cliente.bombeiro
            cliente.militar = get_bool("MILITAR") if get_bool("MILITAR") is not None else cliente.militar
            cliente.iat = get_bool("IAT") if get_bool("IAT") is not None else cliente.iat
            cliente.psicologo = get_bool("PSICOLOGO") if get_bool("PSICOLOGO") is not None else cliente.psicologo
            cliente.atirador_n1 = get_bool("Atirador - Nível 1") if get_bool("Atirador - Nível 1") is not None else cliente.atirador_n1
            cliente.atirador_n2 = get_bool("Atirador - Nível 2") if get_bool("Atirador - Nível 2") is not None else cliente.atirador_n2
            cliente.atirador_n3 = get_bool("Atirador - Nível 3") if get_bool("Atirador - Nível 3") is not None else cliente.atirador_n3

            # Salva dados principais para garantir o ID
            db.session.flush()

            # --- ENDEREÇOS ---
            EnderecoCliente.query.filter_by(cliente_id=cliente.id).delete()
            
            for tipo in ["End1", "End2", "End3"]:
                cep = safe_str(row.get(f"{tipo} - CEP"))
                rua = safe_str(row.get(f"{tipo} - Rua"))
                cidade = safe_str(row.get(f"{tipo} - Cidade"))
                
                if cep or rua or cidade:
                    endereco = EnderecoCliente(
                        cliente_id=cliente.id,
                        tipo="residencial" if tipo == "End1" else "comercial",
                        cep=cep,
                        estado=safe_str(row.get(f"{tipo} - Estado")),
                        cidade=cidade,
                        bairro=safe_str(row.get(f"{tipo} - Bairro")),
                        logradouro=rua,
                        numero=safe_str(row.get(f"{tipo} - Número")),
                        complemento=safe_str(row.get(f"{tipo} - Complemento")),
                    )
                    db.session.add(endereco)

            # --- CONTATOS ---
            ContatoCliente.query.filter_by(cliente_id=cliente.id).delete()
            
            mapa_contatos = [
                ("Telefone", "telefone"),
                ("Telefone 2", "celular"),
                ("Telefone 3", "whatsapp"),
                ("E-mail", "email"),
                ("E-mail 2", "email"),
            ]

            for coluna_excel, tipo_banco in mapa_contatos:
                valor = safe_str(row.get(coluna_excel))
                if valor:
                    contato = ContatoCliente(
                        cliente_id=cliente.id,
                        tipo=tipo_banco,
                        valor=valor,
                    )
                    db.session.add(contato)
            
            total_importados += 1

        db.session.commit()
        print(f"🎉 Importação concluída! {total_importados} clientes processados.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        caminho = sys.argv[1]
    else:
        caminho = os.path.join(os.path.dirname(__file__), "..", "pessoas-29092025.xlsx")
        if not os.path.exists(caminho):
             caminho = os.path.join(os.path.dirname(__file__), "..", "pessoas-29092025.xlsx - Sheet1.csv")

    if os.path.exists(caminho):
        print(f"📂 Importando clientes do arquivo: {caminho}")
        importar_clientes(caminho)
    else:
        print(f"❌ Arquivo não encontrado: {caminho}")