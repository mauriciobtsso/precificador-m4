from app.models import Taxa
from app import db

def test_listar_taxas_vazio(client):
    resp = client.get("/taxas/")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "Nenhuma taxa cadastrada" in text or "taxas" in text.lower()

def test_criar_editar_excluir_taxa(client, app):
    # Criar
    resp = client.post("/taxas/nova", data={
        "numero_parcelas": "3",
        "juros": "5.5"
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Taxa salva com sucesso" in resp.get_data(as_text=True)

    with app.app_context():
        taxa = Taxa.query.filter_by(numero_parcelas=3).first()
        assert taxa is not None
        taxa_id = taxa.id

    # Editar
    resp = client.post(f"/taxas/editar/{taxa_id}", data={
        "numero_parcelas": "4",
        "juros": "7.5"
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "Taxa salva com sucesso" in resp.get_data(as_text=True)

    # Excluir
    resp = client.get(f"/taxas/excluir/{taxa_id}", follow_redirects=True)
    assert resp.status_code == 200
    assert "Taxa excluída com sucesso" in resp.get_data(as_text=True)
