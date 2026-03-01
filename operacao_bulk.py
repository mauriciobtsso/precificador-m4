import csv
import os
from app import create_app, db
from app.produtos.models import Produto
from sqlalchemy import or_

def exportar_para_excel():
    app = create_app()
    with app.app_context():
        # Busca produtos com qualquer pendência nos campos de e-commerce
        produtos = Produto.query.filter(
            or_(
                Produto.nome_comercial == None, Produto.nome_comercial == '',
                Produto.slug == None, Produto.slug == '',
                Produto.meta_title == None, Produto.meta_title == '',
                Produto.descricao_comercial == None, Produto.descricao_comercial == '',
                Produto.descricao_longa == None, Produto.descricao_longa == ''
            )
        ).all()

        if not produtos:
            print("✅ Nada para exportar. Todos os produtos estão 100% equipados!")
            return

        filename = 'planilha_m4_ecommerce.csv'
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';') 
            # Cabeçalho atualizado com todos os campos solicitados
            writer.writerow([
                'ID', 
                'SKU', 
                'NOME_INTERNO', 
                'NOME_LOJA_AMIGAVEL', 
                'CAMINHO_URL_SLUG', 
                'RESUMO_VENDA', 
                'META_TITLE', 
                'META_DESCRIPTION', 
                'FICHA_TECNICA_HTML'
            ])
            
            for p in produtos:
                writer.writerow([
                    p.id, 
                    p.codigo, 
                    p.nome, 
                    p.nome_comercial or '', 
                    p.slug or '',
                    p.descricao_comercial or '', 
                    p.meta_title or '', 
                    p.meta_description or '',
                    p.descricao_longa or ''
                ])
        
        print(f"🚀 Alvos exportados: {len(produtos)} itens em '{filename}'.")

def importar_do_excel():
    app = create_app()
    filename = 'planilha_m4_ecommerce.csv'
    
    if not os.path.exists(filename):
        print(f"❌ Erro: O arquivo '{filename}' não foi encontrado.")
        return

    with app.app_context():
        with open(filename, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            count = 0
            for row in reader:
                # PULO DO GATO: Verifica se a linha tem ID e se não está em branco
                if not row.get('ID') or row['ID'].strip() == '':
                    continue
                
                try:
                    p = db.session.get(Produto, int(row['ID'])) # Usando a sintaxe moderna Session.get
                    if p:
                        p.nome_comercial = row['NOME_LOJA_AMIGAVEL']
                        
                        if row['CAMINHO_URL_SLUG']:
                            p.slug = row['CAMINHO_URL_SLUG']
                            
                        p.descricao_comercial = row['RESUMO_VENDA']
                        p.meta_title = row['META_TITLE']
                        p.meta_description = row['META_DESCRIPTION']
                        p.descricao_longa = row['FICHA_TECNICA_HTML']
                        
                        count += 1
                except ValueError:
                    print(f"⚠️ Ignorando linha com ID inválido: {row.get('ID')}")
                    continue
            
            db.session.commit()
            print(f"✅ Missão Concluída! {count} produtos atualizados com sucesso.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == 'exportar':
            exportar_para_excel()
        elif sys.argv[1] == 'importar':
            importar_do_excel()
    else:
        print("Uso: python operacao_bulk.py [exportar|importar]")