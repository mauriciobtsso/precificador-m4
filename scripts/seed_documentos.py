# scripts/seed_documentos.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import ModeloDocumento

app = create_app()

# --- CONTEÚDOS JÁ CONVERTIDOS PARA HTML/JINJA ---

CONTRATO_ARMA = """
<div style="text-align: center;">
    <img src="{{ empresa.logo }}" width="150"><br>
    <b>{{ empresa.razao_social }}</b> ({{ empresa.cnpj }})<br>
    {{ empresa.telefone }} / {{ empresa.email }}<br>
    Endereço: {{ empresa.endereco }}<br>
    CR: {{ empresa.cr }}
</div>
<br><hr><br>
<h4 style="text-align: center;">CONTRATO DE COMPRA E VENDA DE ARMA DE FOGO</h4>
<p><b>VENDEDOR:</b> {{ empresa.razao_social }}, inscrito no CNPJ {{ empresa.cnpj }}, CR {{ empresa.cr }}.</p>
<p><b>COMPRADOR:</b> {{ cliente.nome }}, CPF {{ cliente.documento }}, RG {{ cliente.rg }} {{ cliente.rg_emissor }}, residente em {{ cliente.endereco_completo }}, Tel: {{ cliente.telefone }}.</p>

<p><b>DO OBJETO:</b><br>
Venda dos itens abaixo:<br>
{{ itens_lista }}
</p>

<p><b>VALOR:</b> R$ {{ venda.valor_total }} (Pago conforme condições acordadas).</p>

<p><b>CLÁUSULAS GERAIS:</b><br>
1. A entrega da arma está condicionada à apresentação da Autorização de Compra/CRAF/GT conforme legislação.<br>
2. O comprador declara estar ciente de todas as exigências legais.</p>

<br><br>
<div style="text-align: center;">
    Teresina, {{ data_hoje }}<br><br><br>
    _____________________________________<br>
    <b>{{ empresa.razao_social }}</b><br><br>
    _____________________________________<br>
    <b>{{ cliente.nome }}</b>
</div>
"""

SERVICO_DESPACHANTE = """
<h3 style="text-align: center;">CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE ASSESSORIA DOCUMENTAL</h3>
<p><b>CONTRATADO:</b> MAURICIO BATISTA DE SOUSA, despachante, endereço AV UNIVERSITÁRIA, 750, TERESINA-PI.</p>
<p><b>CONTRATANTE:</b> {{ cliente.nome }}, CPF {{ cliente.documento }}, RG {{ cliente.rg }}, residente em {{ cliente.endereco_completo }}.</p>

<p><b>CLÁUSULA PRIMEIRA - DO OBJETO:</b><br>
Assessoria para elaboração e protocolo de processo administrativo para AQUISIÇÃO/RENOVAÇÃO/TRANSFERÊNCIA DE ARMA DE FOGO.</p>

<p><b>CLÁUSULA SEGUNDA - DO PREÇO:</b><br>
O valor total dos serviços é de R$ {{ venda.valor_total }}.</p>

<p><b>CLÁUSULA TERCEIRA - OBRIGAÇÕES:</b><br>
O Contratante deve fornecer documentos verídicos. O Contratado obriga-se a instruir o processo corretamente (obrigação de meio, não de fim).</p>

<br><br>
<div style="text-align: center;">
    Teresina, {{ data_hoje }}<br><br>
    _____________________________________<br>
    CONTRATANTE: {{ cliente.nome }}
</div>
"""

RETIRADA_ARMA = """
<h3 style="text-align: center;">TERMO DE RETIRADA DE ARMA DE FOGO</h3>
<p>Eu, <b>{{ cliente.nome }}</b>, CPF <b>{{ cliente.documento }}</b>, declaro ter retirado a(s) arma(s) abaixo descrita(s) no estabelecimento {{ empresa.razao_social }}, na data de <b>{{ data_hoje }}</b>.</p>

<p><b>ITENS RETIRADOS:</b><br>
{{ itens_lista }}</p>

<p>Declaro estar de posse da documentação legal necessária (CRAF e Guia de Trânsito) para o transporte até meu local de guarda.</p>

<br><br>
<div style="text-align: center;">
    _____________________________________<br>
    {{ cliente.nome }}
</div>
"""

RETIRADA_MUNICAO = """
<h3 style="text-align: center;">TERMO DE RETIRADA DE MUNIÇÃO</h3>
<p>Eu, <b>{{ cliente.nome }}</b>, CPF <b>{{ cliente.documento }}</b>, CR <b>{{ cliente.cr }}</b>, declaro ter adquirido e retirado as munições abaixo:</p>

<p>{{ itens_lista }}</p>

<p>Declaro que as quantidades não ultrapassam meus limites legais conforme legislação vigente (Decreto 11.615/2023 e Portaria 166 COLOG).</p>

<br><br>
<div style="text-align: center;">
    Teresina, {{ data_hoje }}<br><br>
    _____________________________________<br>
    {{ cliente.nome }}
</div>
"""

def seed():
    with app.app_context():
        # Lista de Modelos
        dados = [
            {"chave": "contrato_arma", "titulo": "Contrato Venda de Arma", "conteudo": CONTRATO_ARMA},
            {"chave": "servico_despachante", "titulo": "Contrato Despachante", "conteudo": SERVICO_DESPACHANTE},
            {"chave": "retirada_arma", "titulo": "Termo de Retirada (Arma)", "conteudo": RETIRADA_ARMA},
            {"chave": "retirada_municao", "titulo": "Termo de Retirada (Munição)", "conteudo": RETIRADA_MUNICAO},
        ]

        for d in dados:
            existente = ModeloDocumento.query.filter_by(chave=d['chave']).first()
            if not existente:
                m = ModeloDocumento(**d)
                db.session.add(m)
                print(f"Criado: {d['titulo']}")
            else:
                print(f"Já existe: {d['titulo']}")
        
        db.session.commit()
        print("Concluído!")

if __name__ == "__main__":
    seed()