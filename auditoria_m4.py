from app import create_app, db
from app.produtos.models import Produto
from sqlalchemy import or_, and_

def executar_auditoria():
    app = create_app()
    with app.app_context():
        
        # 1. Pendências Gerais (Para todos os produtos)
        condicao_base = or_(
            Produto.nome_comercial == None, Produto.nome_comercial == '',
            Produto.slug == None, Produto.slug == '',
            Produto.descricao_comercial == None, Produto.descricao_comercial == '',
            Produto.descricao_longa == None, Produto.descricao_longa == '',
            Produto.meta_title == None, Produto.meta_title == '',
            Produto.meta_description == None, Produto.meta_description == ''
        )
        
        # 2. Pendências Específicas para Armas (Exige Peso e Comprimento > 0)
        condicao_arma = and_(
            # Considera arma se tem funcionamento OU se exige documentação e tem calibre
            or_(Produto.funcionamento_id != None, and_(Produto.requer_documentacao == True, Produto.calibre_id != None)),
            # Se for arma, verifica se peso ou comprimento estão zerados/nulos
            or_(Produto.peso == None, Produto.peso <= 0, Produto.comprimento == None, Produto.comprimento <= 0)
        )

        # Busca todos que caem na condição geral OU na condição de arma
        pendentes = Produto.query.filter(or_(condicao_base, condicao_arma)).all()

        print(f"\n{'='*60}")
        print(f"📊 RELATÓRIO DE PENDÊNCIAS E-COMMERCE E TÉCNICAS - M4 TÁTICA")
        print(f"{'='*60}")
        print(f"Total de produtos com pendências: {len(pendentes)}\n")

        for p in pendentes:
            faltando = []
            
            # Checagem base
            if not p.nome_comercial: faltando.append("NOME COMERCIAL")
            if not p.slug: faltando.append("SLUG (URL)")
            if not p.descricao_comercial: faltando.append("RESUMO DE VENDA")
            if not p.descricao_longa: faltando.append("FICHA TÉCNICA")
            if not p.meta_title: faltando.append("META TITLE")
            if not p.meta_description: faltando.append("META DESCRIPTION")
            
            # Checagem arma
            eh_arma = bool(p.funcionamento_id) or (p.requer_documentacao and bool(p.calibre_id))
            if eh_arma:
                if not p.peso or p.peso <= 0: faltando.append("PESO (KG)")
                if not p.comprimento or p.comprimento <= 0: faltando.append("COMPRIMENTO (CM)")

            print(f"SKU: {p.codigo} | Original: {p.nome}")
            print(f"🚨 FALTANDO: {', '.join(faltando)}")
            print("-" * 60)

if __name__ == "__main__":
    executar_auditoria()