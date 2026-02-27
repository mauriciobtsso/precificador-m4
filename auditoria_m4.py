from app import create_app, db
from app.produtos.models import Produto
from sqlalchemy import or_

def executar_auditoria():
    app = create_app()
    with app.app_context():
        # Filtra produtos que faltam informações cruciais para a loja
        pendentes = Produto.query.filter(
            or_(
                Produto.nome_comercial == None, Produto.nome_comercial == '',
                Produto.slug == None, Produto.slug == '',
                Produto.descricao_comercial == None, Produto.descricao_comercial == '',
                Produto.descricao_longa == None, Produto.descricao_longa == '',
                Produto.meta_title == None, Produto.meta_title == '',
                Produto.meta_description == None, Produto.meta_description == ''
            )
        ).all()

        print(f"\n{'='*60}")
        print(f"📊 RELATÓRIO DE PENDÊNCIAS E-COMMERCE - M4 TÁTICA")
        print(f"{'='*60}")
        print(f"Total de produtos com pendências: {len(pendentes)}\n")

        for p in pendentes:
            faltando = []
            if not p.nome_comercial: faltando.append("NOME COMERCIAL")
            if not p.slug: faltando.append("SLUG (URL)")
            if not p.descricao_comercial: faltando.append("RESUMO DE VENDA")
            if not p.descricao_longa: faltando.append("FICHA TÉCNICA (HTML)")
            if not p.meta_title: faltando.append("META TITLE")
            if not p.meta_description: faltando.append("META DESCRIPTION")

            print(f"SKU: {p.codigo} | Original: {p.nome}")
            print(f"🚨 FALTANDO: {', '.join(faltando)}")
            print("-" * 60)

if __name__ == "__main__":
    executar_auditoria()