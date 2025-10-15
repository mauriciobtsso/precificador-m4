# criar_estrutura_produtos.py
import os, textwrap

base = "app/produtos"

estruturas = [
    f"{base}/templates",
    f"{base}/categorias/templates",
    f"{base}/categorias/static/js",
    f"{base}/precificacao/templates",
    f"{base}/precificacao/static/js",
]

for pasta in estruturas:
    os.makedirs(pasta, exist_ok=True)

arquivos = {
    f"{base}/__init__.py": textwrap.dedent("""
        from flask import Blueprint

        produtos_bp = Blueprint("produtos", __name__, url_prefix="/produtos")

        from app.produtos import routes
        from app.produtos.categorias.routes import categorias_bp
        from app.produtos.precificacao.routes import precificacao_bp

        produtos_bp.register_blueprint(categorias_bp)
        produtos_bp.register_blueprint(precificacao_bp)
    """),

    f"{base}/models.py": textwrap.dedent("""
        from app import db

        class Produto(db.Model):
            __tablename__ = "produto"
            id = db.Column(db.Integer, primary_key=True)
            nome = db.Column(db.String(150), nullable=False)
            categoria_id = db.Column(db.Integer, db.ForeignKey("categoria_produto.id"))
            preco_custo = db.Column(db.Numeric(10,2))
            preco_venda = db.Column(db.Numeric(10,2))
            margem = db.Column(db.Numeric(5,2))
            ativo = db.Column(db.Boolean, default=True)

            categoria = db.relationship("CategoriaProduto", backref="produtos")

            def __repr__(self):
                return f"<Produto {self.nome}>"
    """),

    f"{base}/routes.py": 'from flask import render_template\nfrom app.produtos import produtos_bp\n\n@produtos_bp.route("/")\ndef index():\n    return render_template("produtos.html")\n',
    f"{base}/templates/produtos.html": '<h2>Produtos</h2>',
    f"{base}/categorias/__init__.py": 'from flask import Blueprint\n\ncategorias_bp = Blueprint("categorias", __name__, url_prefix="/categorias", template_folder="templates", static_folder="static")\n',
    f"{base}/categorias/models.py": 'from app import db\n\nclass CategoriaProduto(db.Model):\n    __tablename__ = "categoria_produto"\n    id = db.Column(db.Integer, primary_key=True)\n    nome = db.Column(db.String(100))\n',
    f"{base}/categorias/routes.py": 'from flask import render_template\nfrom app.produtos.categorias import categorias_bp\n\n@categorias_bp.route("/")\ndef index():\n    return render_template("categorias.html")\n',
    f"{base}/categorias/templates/categorias.html": '<h2>Categorias</h2>',
    f"{base}/precificacao/__init__.py": 'from flask import Blueprint\n\nprecificacao_bp = Blueprint("precificacao", __name__, url_prefix="/precificacao", template_folder="templates", static_folder="static")\n',
    f"{base}/precificacao/routes.py": 'from flask import render_template, jsonify, request\nfrom app.produtos.precificacao import precificacao_bp\nfrom app.services.precificacao_service import calcular_precificacao\n\n@precificacao_bp.route("/")\ndef view():\n    return render_template("precificacao.html")\n\n@precificacao_bp.route("/api/precificar", methods=["POST"])\ndef api():\n    data = request.get_json()\n    resultado = calcular_precificacao(**data)\n    return jsonify(resultado)\n',
    f"{base}/precificacao/templates/precificacao.html": '<h2>Precificação Rápida</h2>',
    "app/services/precificacao_service.py": 'def calcular_precificacao(custo=0, frete=0, margem=0, **kw):\n    custo_total = float(custo) + float(frete)\n    venda = custo_total * (1 + float(margem)/100)\n    return dict(custo_total=custo_total, preco_venda=venda, lucro=venda-custo_total)\n',
}

for path, content in arquivos.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")

print("✅ Estrutura criada com sucesso!")
