def test_central_importacoes_abre_com_schema_atual(client):
    response = client.get("/importacoes/")
    assert response.status_code == 200
    assert "Central de Importações" in response.get_data(as_text=True)
