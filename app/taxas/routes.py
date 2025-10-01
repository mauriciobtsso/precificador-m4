from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models import Taxa
from app.utils.converters import to_float
from app.utils.db_helpers import get_or_404

taxas_bp = Blueprint("taxas", __name__, url_prefix="/taxas")


# =========================
# LISTAR
# =========================
@taxas_bp.route("/", methods=["GET"])
@login_required
def listar():
    taxas = db.session.query(Taxa).order_by(Taxa.numero_parcelas).all()
    return render_template("taxas.html", taxas=taxas)


# =========================
# NOVA / EDITAR
# =========================
@taxas_bp.route("/nova", methods=["GET", "POST"])
@taxas_bp.route("/editar/<int:taxa_id>", methods=["GET", "POST"])
@login_required
def gerenciar(taxa_id=None):
    taxa = db.session.get(Taxa, taxa_id) if taxa_id else None

    if request.method == "POST":
        if not taxa:
            taxa = Taxa()
            db.session.add(taxa)

        numero_parcelas_raw = request.form.get("numero_parcelas")
        juros_raw = request.form.get("juros")

        taxa.numero_parcelas = int(numero_parcelas_raw or (taxa.numero_parcelas or 1))
        taxa.juros = to_float(juros_raw, default=(taxa.juros or 0))

        db.session.commit()
        flash("Taxa salva com sucesso!", "success")
        return redirect(url_for("taxas.listar"))

    return render_template("taxa_form.html", taxa=taxa)


# =========================
# EXCLUIR
# =========================
@taxas_bp.route("/excluir/<int:taxa_id>")
@login_required
def excluir(taxa_id):
    taxa = get_or_404(Taxa, taxa_id)
    db.session.delete(taxa)
    db.session.commit()
    flash("Taxa excluída com sucesso!", "success")
    return redirect(url_for("taxas.listar"))