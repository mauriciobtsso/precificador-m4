from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    users = User.query.all()
    if not users:
        print("Nenhum usuário encontrado na tabela 'users'.")
    else:
        for user in users:
            # Se já estiver hasheada (começa com pbkdf2), ignora
            if not user.password_hash.startswith("pbkdf2:"):
                plain = user.password_hash
                user.password_hash = generate_password_hash(plain)
                print(f"[OK] Convertida senha do usuário: {user.username}")
            else:
                print(f"[SKIP] Usuário {user.username} já está com senha hasheada.")

        db.session.commit()
        print("✅ Todas as senhas foram migradas com sucesso!")
