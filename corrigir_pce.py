from app import create_app, db
from app.produtos.models import Produto
from sqlalchemy import or_

def classificar_armas_pce():
    app = create_app()
    with app.app_context():
        print("🔍 Iniciando varredura de arsenal...")
        
        # Palavras-chave que definem um PCE (Produto Controlado pelo Exército)
        termos_pce = ['PISTOLA', 'REVOLVER', 'REV ', 'PIST ', 'RIFLE', 'CARABINA', 'ESPINGARDA', 'FUZIL']
        
        # Filtros para busca
        filtros = [Produto.nome.ilike(f'%{termo}%') for termo in termos_pce]
        filtros += [Produto.nome_comercial.ilike(f'%{termo}%') for termo in termos_pce]
        
        # Busca todos os produtos que batem com a descrição de arma de fogo
        armas = Produto.query.filter(or_(*filtros)).all()
        
        count = 0
        for arma in armas:
            # Aqui você deve usar o nome exato do campo no seu Model (geralmente 'requer_documentacao')
            if hasattr(arma, 'requer_documentacao'):
                arma.requer_documentacao = True
                count += 1
                print(f"✅ [MARCADO COMO PCE]: {arma.nome_comercial or arma.nome}")
        
        db.session.commit()
        print(f"\n🚀 Missão cumprida! {count} armas foram configuradas com exigência de CR/Documentação.")

if __name__ == "__main__":
    classificar_armas_pce()