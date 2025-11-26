import sys
import os
from sqlalchemy import func, text

# Adiciona a raiz do projeto ao caminho
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.clientes.models import Cliente, EnderecoCliente, ContatoCliente, Documento, Arma, Comunicacao, Processo
from app.vendas.models import Venda
from app.estoque.models import ItemEstoque

def normalizar(texto):
    """Remove espaços extras e converte para minúsculo para comparação"""
    if not texto:
        return ""
    return " ".join(str(texto).strip().lower().split())

def mesclar_clientes(principal, duplicado):
    """
    Move todos os relacionamentos do cliente 'duplicado' para o 'principal'
    e depois exclui o duplicado.
    """
    print(f"   ↳ Mesclando: (ID {duplicado.id}) '{duplicado.nome}' -> (ID {principal.id}) '{principal.nome}'")

    # 1. Migrar Vendas
    vendas_migradas = Venda.query.filter_by(cliente_id=duplicado.id).update({'cliente_id': principal.id})
    
    # 2. Migrar Armas
    armas_migradas = Arma.query.filter_by(cliente_id=duplicado.id).update({'cliente_id': principal.id})
    
    # 3. Migrar Documentos (Anexos)
    docs_migrados = Documento.query.filter_by(cliente_id=duplicado.id).update({'cliente_id': principal.id})
    
    # 4. Migrar Processos
    procs_migrados = Processo.query.filter_by(cliente_id=duplicado.id).update({'cliente_id': principal.id})
    
    # 5. Migrar Comunicações
    coms_migradas = Comunicacao.query.filter_by(cliente_id=duplicado.id).update({'cliente_id': principal.id})
    
    # 6. Migrar Estoque (Fornecedor)
    estoque_migrado = ItemEstoque.query.filter_by(fornecedor_id=duplicado.id).update({'fornecedor_id': principal.id})

    # 7. Migrar Endereços e Contatos (Pode gerar duplicidade, mas melhor sobrar que faltar)
    end_migrados = EnderecoCliente.query.filter_by(cliente_id=duplicado.id).update({'cliente_id': principal.id})
    cont_migrados = ContatoCliente.query.filter_by(cliente_id=duplicado.id).update({'cliente_id': principal.id})

    # Preencher dados faltantes no Principal com dados do Duplicado
    if not principal.documento and duplicado.documento: principal.documento = duplicado.documento
    if not principal.cr and duplicado.cr: principal.cr = duplicado.cr
    if not principal.data_nascimento and duplicado.data_nascimento: principal.data_nascimento = duplicado.data_nascimento
    
    # Deletar o duplicado
    db.session.delete(duplicado)
    
    total = vendas_migradas + armas_migradas + docs_migrados + procs_migrados
    return total

def limpar_duplicados():
    app = create_app()
    with app.app_context():
        print("🔍 Iniciando varredura de duplicatas...")
        
        # --- ESTRATÉGIA 1: Duplicatas por NOME (Case Insensitive) ---
        todos_clientes = Cliente.query.order_by(Cliente.id).all()
        mapa_nomes = {}
        duplicatas_removidas = 0

        print("\n1️⃣ Verificando duplicatas por NOME...")
        
        # Agrupa IDs por nome normalizado
        for c in todos_clientes:
            if not c.nome: continue
            nome_norm = normalizar(c.nome)
            
            if nome_norm not in mapa_nomes:
                mapa_nomes[nome_norm] = []
            mapa_nomes[nome_norm].append(c)

        # Processa os grupos que têm mais de 1 cliente
        for nome, lista in mapa_nomes.items():
            if len(lista) > 1:
                print(f"\n⚠️ Encontrados {len(lista)} registros para: '{lista[0].nome}'")
                
                # Critério de escolha do PRINCIPAL: 
                # 1. O que tem CPF/CNPJ preenchido
                # 2. Se empate, o ID mais antigo (o primeiro criado)
                
                principal = None
                # Tenta achar um com documento
                for cand in lista:
                    if cand.documento:
                        principal = cand
                        break
                
                # Se nenhum tem documento, pega o primeiro da lista (ID menor)
                if not principal:
                    principal = lista[0]

                # Todos os outros são duplicatas
                for duplicado in lista:
                    if duplicado.id != principal.id:
                        mesclar_clientes(principal, duplicado)
                        duplicatas_removidas += 1

        db.session.commit()
        print(f"\n✅ Limpeza por nomes concluída. {duplicatas_removidas} clientes fundidos.")

        # --- ESTRATÉGIA 2: Duplicatas por DOCUMENTO (para garantir) ---
        # (Geralmente o banco bloqueia, mas se tiver espaços ou pontuação diferente pode passar)
        print("\n2️⃣ Verificando duplicatas por DOCUMENTO (CPF/CNPJ)...")
        
        # Recarrega lista
        todos_clientes = Cliente.query.filter(Cliente.documento != None).order_by(Cliente.id).all()
        mapa_docs = {}
        dups_docs = 0

        def limpar_doc(d):
            return "".join(filter(str.isdigit, str(d)))

        for c in todos_clientes:
            doc_limpo = limpar_doc(c.documento)
            if not doc_limpo: continue
            
            if doc_limpo not in mapa_docs:
                mapa_docs[doc_limpo] = []
            mapa_docs[doc_limpo].append(c)

        for doc, lista in mapa_docs.items():
            if len(lista) > 1:
                print(f"\n⚠️ CPF/CNPJ Duplicado detectado: {doc}")
                principal = lista[0] # ID menor
                
                for duplicado in lista[1:]:
                    if duplicado.id != principal.id:
                        mesclar_clientes(principal, duplicado)
                        dups_docs += 1

        db.session.commit()
        print(f"\n🎉 Processo finalizado! Total removido: {duplicatas_removidas + dups_docs}")

if __name__ == "__main__":
    if input("Isso vai mesclar e apagar clientes duplicados. Digite 'SIM' para continuar: ") == "SIM":
        limpar_duplicados()
    else:
        print("Operação cancelada.")