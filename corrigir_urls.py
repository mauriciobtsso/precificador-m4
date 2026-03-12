from app import create_app, db

app = create_app()

URL_ERRADA = "https://pub-1202e2896f1ad48f3caa5d520ab29ff0.r2.dev/"
URL_CORRETA = "https://cdn.m4tatica.com.br/"

with app.app_context():
    result = db.session.execute(
        db.text(
            "UPDATE produtos SET foto_url = REPLACE(foto_url, :errada, :correta) "
            "WHERE foto_url LIKE :like"
        ),
        {"errada": URL_ERRADA, "correta": URL_CORRETA, "like": URL_ERRADA + "%"}
    )
    db.session.commit()
    print(f"Produtos corrigidos: {result.rowcount}")