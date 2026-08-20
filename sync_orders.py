
import uuid
from app import create_app, db
from app.carrinho.models import Pedido
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("--- Sincronizando Pedidos M4 ---")

    # 0. Garantir que a coluna public_id existe (Resiliência total)
    try:
        db.session.execute(text("SELECT public_id FROM pedidos LIMIT 1"))
    except Exception:
        db.session.rollback()
        print("Coluna 'public_id' não encontrada. Criando...")
        try:
            db.session.execute(text("ALTER TABLE pedidos ADD COLUMN public_id VARCHAR(36) UNIQUE"))
            db.session.execute(text("CREATE INDEX idx_pedidos_public_id ON pedidos (public_id)"))
            db.session.commit()
            print("Coluna 'public_id' criada com sucesso.")
        except Exception as e:
            print(f"Erro ao criar coluna: {e}")
            db.session.rollback()
    
    # 1. Backfill public_id para pedidos existentes
    pedidos_sem_uuid = Pedido.query.filter(Pedido.public_id == None).all()
    if pedidos_sem_uuid:
        print(f"Gerando IDs públicos para {len(pedidos_sem_uuid)} pedidos...")
        for p in pedidos_sem_uuid:
            p.public_id = str(uuid.uuid4())
        db.session.commit()
        print("IDs públicos gerados com sucesso.")
    else:
        print("Todos os pedidos já possuem IDs públicos.")

    # 2. Ajustar a sequência para 328
    try:
        # Pega o nome da sequência da tabela pedidos
        result = db.session.execute(text("SELECT pg_get_serial_sequence('pedidos', 'id')")).fetchone()
        seq_name = result[0]
        
        if seq_name:
            print(f"Ajustando sequência {seq_name} para iniciar em 328...")
            # O terceiro parâmetro 'false' faz com que o PRÓXIMO valor seja 328
            db.session.execute(text(f"SELECT setval('{seq_name}', 328, false)"))
            db.session.commit()
            print("Sequência ajustada com sucesso. Próximo pedido será o #328.")
        else:
            print("Não foi possível localizar a sequência automática para a tabela 'pedidos'.")
    except Exception as e:
        print(f"Erro ao ajustar sequência: {e}")
        db.session.rollback()

    print("--- Operação Concluída ---")
