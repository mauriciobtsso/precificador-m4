import pandas as pd
from datetime import datetime
from app import create_app, db
from app.clientes.models import ContatoCliente

# Cria app e contexto
app = create_app()
app.app_context().push()

# Carregar planilha
df = pd.read_excel("contatos.xlsx")

print("Colunas encontradas:", df.columns)

# Normalizar nomes das colunas
df.columns = [c.lower().strip() for c in df.columns]

# Esperado: id, nome, telefone, e-mail
for _, row in df.iterrows():
    cliente_id = row["id"]
    telefone = str(row.get("telefone") or "").strip()
    email = str(row.get("e-mail") or "").strip()

    # TELEFONE
    if telefone:
        contato_tel = ContatoCliente.query.filter_by(cliente_id=cliente_id, tipo="telefone").first()
        if contato_tel:
            contato_tel.valor = telefone
            contato_tel.updated_at = datetime.utcnow()
            print(f"Atualizado telefone do cliente {cliente_id}")
        else:
            novo_tel = ContatoCliente(
                cliente_id=cliente_id,
                tipo="telefone",
                valor=telefone,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(novo_tel)
            print(f"Inserido telefone para cliente {cliente_id}")

    # EMAIL
    if email:
        contato_email = ContatoCliente.query.filter_by(cliente_id=cliente_id, tipo="email").first()
        if contato_email:
            contato_email.valor = email
            contato_email.updated_at = datetime.utcnow()
            print(f"Atualizado email do cliente {cliente_id}")
        else:
            novo_email = ContatoCliente(
                cliente_id=cliente_id,
                tipo="email",
                valor=email,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(novo_email)
            print(f"Inserido email para cliente {cliente_id}")

# Commit final
db.session.commit()
print("Importação concluída!")
