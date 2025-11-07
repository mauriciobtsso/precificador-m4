from app import create_app, db
from app.produtos.models import Produto
import requests

app = create_app()
with app.app_context():
    sem_foto, quebradas, validas = [], [], []

    print("🔍 Verificando fotos dos produtos...")

    for p in Produto.query.all():
        url = (p.foto_url or '').strip()
        if not url:
            sem_foto.append(p)
            continue
        try:
            resp = requests.head(url, timeout=5)
            if resp.status_code == 200:
                validas.append(p)
            else:
                quebradas.append(p)
        except Exception:
            quebradas.append(p)

    print("\n--- RELATÓRIO DE FOTOS DE PRODUTOS ---")
    print(f"✅ Válidas: {len(validas)}")
    print(f"⚠️  Quebradas: {len(quebradas)}")
    print(f"❌ Sem foto: {len(sem_foto)}")

    with open("relatorio_fotos_produtos.txt", "w", encoding="utf-8") as f:
        f.write("=== PRODUTOS COM FOTO INVÁLIDA ===\n")
        for p in quebradas:
            f.write(f"{p.id} - {p.nome} - {p.foto_url}\n")
        f.write("\n=== PRODUTOS SEM FOTO ===\n")
        for p in sem_foto:
            f.write(f"{p.id} - {p.nome}\n")
        f.write("\n=== PRODUTOS COM FOTO OK ===\n")
        for p in validas:
            f.write(f"{p.id} - {p.nome}\n")

    print("\n📄 Relatório salvo em: relatorio_fotos_produtos.txt")
