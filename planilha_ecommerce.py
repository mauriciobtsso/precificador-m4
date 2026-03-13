import csv
import sys
import os
from app import create_app, db
from app.produtos.models import Produto
from sqlalchemy import or_, and_

# Nome do arquivo padrão
ARQUIVO_CSV = 'planilha_m4_ecommerce.csv'

def exportar_pendencias():
    app = create_app()
    with app.app_context():
       # Filtro inteligente: Pega apenas armas com peso ou comprimento zerados
        condicao_arma = and_(
            or_(Produto.funcionamento_id != None, and_(Produto.requer_documentacao == True, Produto.calibre_id != None)),
            ~Produto.categoria.has(CategoriaProduto.slug.ilike('%muni%')),
            ~Produto.categoria.has(CategoriaProduto.slug.ilike('%insumo%')),
            ~Produto.categoria.has(CategoriaProduto.slug.ilike('%carregador%')),
            or_(Produto.peso == None, Produto.peso <= 0, Produto.comprimento == None, Produto.comprimento <= 0)
        )
        
        produtos = Produto.query.filter(condicao_arma).all()
        
        if not produtos:
            print("✅ Nenhuma arma com pendência de peso/comprimento encontrada!")
            return

        with open(ARQUIVO_CSV, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            # Cabeçalho da planilha (NÃO ALTERE O NOME DESTAS COLUNAS NO EXCEL)
            writer.writerow(['ID', 'SKU', 'NOME', 'PESO_KG', 'COMPRIMENTO_CM', 'LARGURA_CM', 'ALTURA_CM'])
            
            for p in produtos:
                # Troca ponto por vírgula para abrir bonito no Excel brasileiro
                peso = str(p.peso or 0).replace('.', ',')
                comp = str(p.comprimento or 0).replace('.', ',')
                larg = str(p.largura or 0).replace('.', ',')
                alt = str(p.altura or 0).replace('.', ',')
                
                writer.writerow([p.id, p.codigo, p.nome, peso, comp, larg, alt])
                
        print(f"📦 Planilha gerada com sucesso: {ARQUIVO_CSV}")
        print(f"Total de produtos exportados: {len(produtos)}")


def importar_planilha():
    if not os.path.exists(ARQUIVO_CSV):
        print(f"❌ Arquivo '{ARQUIVO_CSV}' não encontrado! Exporte primeiro.")
        return

    app = create_app()
    with app.app_context():
        count_atualizados = 0
        
        with open(ARQUIVO_CSV, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            
            for row in reader:
                try:
                    produto_id = int(row['ID'])
                    p = Produto.query.get(produto_id)
                    
                    if p:
                        # Converte a vírgula de volta para ponto antes de salvar no banco
                        p.peso = float(row['PESO_KG'].replace(',', '.')) if row['PESO_KG'] else 0.0
                        p.comprimento = float(row['COMPRIMENTO_CM'].replace(',', '.')) if row['COMPRIMENTO_CM'] else 0.0
                        p.largura = float(row['LARGURA_CM'].replace(',', '.')) if row['LARGURA_CM'] else 0.0
                        p.altura = float(row['ALTURA_CM'].replace(',', '.')) if row['ALTURA_CM'] else 0.0
                        
                        count_atualizados += 1
                        print(f"Atualizando: {p.codigo} - {p.nome}")
                        
                except Exception as e:
                    print(f"⚠️ Erro ao atualizar linha ID {row.get('ID', 'Desconhecido')}: {str(e)}")
                    
        try:
            db.session.commit()
            print("="*40)
            print(f"✅ SUCESSO! {count_atualizados} produtos atualizados no banco de dados.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erro crítico ao salvar no banco: {str(e)}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso incorreto. Comandos disponíveis:")
        print("  python planilha_ecommerce.py exportar")
        print("  python planilha_ecommerce.py importar")
        sys.exit(1)
        
    comando = sys.argv[1].lower()
    
    if comando == 'exportar':
        exportar_pendencias()
    elif comando == 'importar':
        importar_planilha()
    else:
        print("Comando inválido. Use 'exportar' ou 'importar'.")