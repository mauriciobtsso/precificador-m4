# scripts/seed_documentos.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import ModeloDocumento

app = create_app()

# ==============================================================================
# 1. TERMO DE RETIRADA DE MUNIÇÃO (LAYOUT "TIRO DIGITAL")
# ==============================================================================
RETIRADA_MUNICAO = """
<style>
    body { font-family: Arial, Helvetica, sans-serif; font-size: 12px; color: #000; }
    .container-doc { width: 100%; }
    
    /* Cabeçalho */
    .header-table { width: 100%; border-collapse: collapse; margin-bottom: 15px; }
    .header-table td { vertical-align: top; }
    .logo-img { max-width: 120px; max-height: 80px; }
    .company-info { font-size: 11px; line-height: 1.3; padding-left: 15px; }
    
    /* Títulos */
    .section-title { 
        background-color: #e0e0e0; 
        border: 1px solid #000; 
        font-weight: bold; 
        text-align: center; 
        padding: 5px; 
        margin-top: 10px; 
        margin-bottom: 0;
        font-size: 13px;
    }
    
    /* Tabelas de Dados */
    .data-table { width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 15px; }
    .data-table td, .data-table th { border: 1px solid #000; padding: 4px 6px; vertical-align: middle; }
    .data-table th { background-color: #f2f2f2; font-weight: bold; text-align: left; }
    .label { font-weight: bold; background-color: #f9f9f9; width: 15%; }
    
    /* Texto Legal */
    .legal-box { 
        font-size: 10px; 
        line-height: 1.4; 
        text-align: justify; 
        margin-top: 10px; 
        border: 1px solid #ccc; 
        padding: 8px;
    }
    
    /* Assinatura */
    .signature-area { margin-top: 50px; text-align: center; }
    .signature-line { width: 60%; margin: 0 auto; border-top: 1px solid #000; padding-top: 5px; }
</style>

<table class="header-table">
    <tr>
        <td width="130"><img src="{{ empresa.logo }}" class="logo-img"></td>
        <td class="company-info">
            <strong style="font-size: 14px;">{{ empresa.razao_social }}</strong><br>
            CNPJ: {{ empresa.cnpj }}<br>
            CR: {{ empresa.cr }}<br>
            {{ empresa.endereco }}<br>
            Contato: {{ empresa.telefone }} | {{ empresa.email }}
        </td>
    </tr>
</table>

<div class="section-title">TERMO DE RETIRADA DE MUNIÇÃO</div>

<div style="font-weight: bold; margin: 10px 0 2px 0;">RETIRADO POR:</div>
<table class="data-table">
    <tr>
        <td class="label">Nome</td>
        <td colspan="3">{{ cliente.nome }}</td>
    </tr>
    <tr>
        <td class="label">CPF/CNPJ</td>
        <td width="35%">{{ cliente.documento }}</td>
        <td class="label">CR</td>
        <td>{{ cliente.cr }} {% if cliente.cr_validade %}(Val: {{ cliente.cr_validade }}){% endif %}</td>
    </tr>
    <tr>
        <td class="label">Endereço</td>
        <td colspan="3">{{ cliente.endereco_completo }}</td>
    </tr>
    <tr>
        <td class="label">Contato</td>
        <td>{{ cliente.telefone }}</td>
        <td class="label">Nota Fiscal</td>
        <td>
            {% if venda.nf_numero %}
                <b>Nº {{ venda.nf_numero }}</b> (Chave: {{ venda.nf_chave or 'N/A' }})
            {% else %}
                <span style="color:red;">PENDENTE DE EMISSÃO</span>
            {% endif %}
        </td>
    </tr>
</table>

<div style="font-weight: bold; margin: 10px 0 2px 0;">ITENS ADQUIRIDOS:</div>
<table class="data-table">
    <thead>
        <tr>
            <th style="text-align: center; width: 8%;">Qtd.</th>
            <th>Descrição do Produto</th>
            <th style="text-align: center; width: 15%;">Lote</th>
            <th style="width: 35%;">Arma Vinculada (CRAF)</th>
        </tr>
    </thead>
    <tbody>
        {% for item in venda.itens %}
        <tr>
            <td style="text-align: center;"><b>{{ item.quantidade }}</b></td>
            <td>
                {{ item.produto_nome }}
            </td>
            <td style="text-align: center;">
                {{ item.item_estoque.lote or '-' }}
            </td>
            <td>
                {% if item.arma_cliente %}
                    <b>{{ item.arma_cliente.tipo }} {{ item.arma_cliente.calibre }}</b><br>
                    <span style="font-size: 9px;">
                        Nº Série: {{ item.arma_cliente.numero_serie }}<br>
                        {% if item.arma_cliente.numero_sigma %}Sigma: {{ item.arma_cliente.numero_sigma }}{% endif %}
                    </span>
                {% else %}
                    <span style="color: #999;">-</span>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>

<div class="legal-box">
    <p style="margin:0; font-weight:bold;">Limites Legais (Decreto 11.615/2023 e Portaria 166 COLOG):</p>
    <ul style="margin: 5px 0; padding-left: 20px;">
        <li>Cidadão Comum: Até 50 munições de calibre permitido por arma/ano.</li>
        <li>CR NÍVEL I: 4.000 munições / 8.000 cartuchos .22 LR / 3kg Pólvora.</li>
        <li>CR NÍVEL II: 8.000 munições / 16.000 cartuchos .22 LR / 6kg Pólvora.</li>
        <li>CR NÍVEL III: 20.000 munições / 6.000 restritas / 32.000 cartuchos .22 LR / 12kg Pólvora.</li>
    </ul>
    <p style="margin:0; font-style: italic;">*Em caso de atualização das normas, valerão as últimas publicadas pelos órgãos reguladores.</p>
    <br>
    <p style="margin:0;">
        Eu, <b>{{ cliente.nome }}</b>, documento nº <b>{{ cliente.rg }}</b>, declaro ter adquirido e retirado os itens detalhados acima nesta data. 
        Declaro possuir permissão legal para esta aquisição e que as quantidades não ultrapassam meus limites permitidos.
        Declaro estar ciente e consinto com a coleta e arquivamento dos meus dados para fins de cumprimento de obrigação legal (LGPD).
    </p>
</div>

<div class="signature-area">
    <br><br>
    Teresina (PI), {{ data_hoje }}
    <br><br><br>
    <div class="signature-line">
        <b>{{ cliente.nome }}</b><br>
        COMPRADOR
    </div>
</div>
"""

# ==============================================================================
# 2. TERMO DE RETIRADA DE ARMA (MANTIDO PADRÃO M4/TIRO DIGITAL)
# ==============================================================================
RETIRADA_ARMA = """
<style>
    body { font-family: Arial, Helvetica, sans-serif; font-size: 12px; color: #000; }
    .header-table { width: 100%; margin-bottom: 20px; border-bottom: 2px solid #000; padding-bottom: 10px; }
    .logo-img { max-width: 150px; }
    .title-box { background: #000; color: #fff; font-weight: bold; text-align: center; padding: 8px; margin: 15px 0; font-size: 14px; }
    .info-row { margin-bottom: 8px; font-size: 12px; }
    .info-label { font-weight: bold; display: inline-block; width: 120px; }
    .product-box { border: 1px solid #000; padding: 10px; margin: 15px 0; background: #fdfdfd; }
    .legal-small { font-size: 10px; text-align: justify; color: #333; margin-top: 20px; border-top: 1px solid #ccc; padding-top: 10px; }
</style>

<table class="header-table">
    <tr>
        <td width="30%"><img src="{{ empresa.logo }}" class="logo-img"></td>
        <td align="right" style="font-size: 11px;">
            <b>{{ empresa.razao_social }}</b><br>
            CNPJ: {{ empresa.cnpj }} | CR: {{ empresa.cr }}<br>
            {{ empresa.endereco }}<br>
            {{ empresa.telefone }}
        </td>
    </tr>
</table>

<div class="title-box">TERMO DE RETIRADA DE ARMA DE FOGO</div>

<div style="margin: 20px 0;">
    <div class="info-row"><span class="info-label">COMPRADOR:</span> {{ cliente.nome }}</div>
    <div class="info-row"><span class="info-label">CPF:</span> {{ cliente.documento }}</div>
    <div class="info-row"><span class="info-label">CR:</span> {{ cliente.cr }}</div>
    <div class="info-row"><span class="info-label">ENDEREÇO:</span> {{ cliente.endereco_completo }}</div>
</div>

<div class="product-box">
    <div style="font-weight: bold; border-bottom: 1px solid #ccc; margin-bottom: 10px;">DADOS DO EQUIPAMENTO</div>
    {% for item in venda.itens %}
    <table width="100%" style="font-size: 12px; margin-bottom: 10px;">
        <tr>
            <td width="20%"><b>Tipo:</b> {{ item.categoria }}</td>
            <td width="30%"><b>Marca:</b> {{ item.produto.marca or 'N/A' }}</td>
            <td width="20%"><b>Calibre:</b> {{ item.produto.calibre or 'N/A' }}</td>
            <td width="30%"><b>Nº Série:</b> {{ item.item_estoque.numero_serie or 'N/A' }}</td>
        </tr>
        <tr>
            <td colspan="4"><b>Modelo/Descrição:</b> {{ item.produto_nome }}</td>
        </tr>
    </table>
    {% endfor %}
</div>

<div class="legal-small">
    <b>DECLARAÇÃO DE RECEBIMENTO E RESPONSABILIDADE:</b><br>
    Declaro que recebi o(s) armamento(s) acima descrito(s) em perfeitas condições de uso e funcionamento.
    Declaro estar de posse do <b>CRAF (Certificado de Registro de Arma de Fogo)</b> e da respectiva <b>Guia de Tráfego/Trânsito</b> ou Porte Funcional que me autoriza o transporte da arma do estabelecimento comercial até o local de guarda autorizado.
    Assumo total responsabilidade civil e criminal pela guarda, transporte e uso do equipamento a partir deste ato.
</div>

<div style="margin-top: 60px; text-align: center;">
    ___________________________________________________________<br>
    <b>{{ cliente.nome }}</b><br>
    CPF: {{ cliente.documento }}
</div>

<div style="text-align: center; margin-top: 30px; font-size: 11px;">
    Teresina (PI), {{ data_hoje }}
</div>
"""

# ==============================================================================
# 3. CONTRATO DE VENDA (ARMA)
# ==============================================================================
CONTRATO_ARMA = """
<style>
    body { font-family: 'Times New Roman', serif; font-size: 12px; line-height: 1.5; }
    h3 { text-align: center; text-decoration: underline; margin-bottom: 20px; }
    p { text-align: justify; margin-bottom: 10px; }
    .clause { font-weight: bold; margin-top: 15px; display: block; }
</style>

<div style="text-align: center; margin-bottom: 20px;">
    <img src="{{ empresa.logo }}" width="100"><br>
    <b>{{ empresa.razao_social }}</b>
</div>

<h3>CONTRATO DE COMPRA E VENDA DE ARMA DE FOGO</h3>

<p><b>VENDEDOR:</b> {{ empresa.razao_social }}, pessoa jurídica de direito privado, inscrita no CNPJ sob o nº {{ empresa.cnpj }}, com sede em {{ empresa.endereco }}, detentora do CR nº {{ empresa.cr }}.</p>

<p><b>COMPRADOR:</b> {{ cliente.nome }}, inscrito no CPF sob o nº {{ cliente.documento }}, RG {{ cliente.rg }} {{ cliente.rg_emissor }}, residente e domiciliado em {{ cliente.endereco_completo }}.</p>

<p>As partes acima identificadas têm, entre si, justo e contratado o presente Contrato de Compra e Venda, que se regerá pelas cláusulas seguintes:</p>

<span class="clause">CLÁUSULA PRIMEIRA - DO OBJETO</span>
<p>O presente contrato tem como objeto a venda do(s) seguinte(s) produto(s):</p>
<div style="border: 1px solid #000; padding: 10px; margin: 10px 0;">
    {{ itens_lista }}
</div>

<span class="clause">CLÁUSULA SEGUNDA - DO PREÇO E PAGAMENTO</span>
<p>O Comprador pagará ao Vendedor a importância total de <b>{{ br_money(venda.valor_total) }}</b>.</p>

<span class="clause">CLÁUSULA TERCEIRA - DA ENTREGA</span>
<p>A entrega do armamento objeto deste contrato está <b>estritamente condicionada</b> à apresentação, pelo COMPRADOR, da autorização de compra deferida pelo órgão competente (Sinarm ou Sigma) e posterior emissão do CRAF (Certificado de Registro de Arma de Fogo) em nome do adquirente.</p>

<span class="clause">CLÁUSULA QUARTA - DAS DISPOSIÇÕES GERAIS</span>
<p>O COMPRADOR declara estar ciente de todas as exigências legais previstas na Lei 10.826/2003 (Estatuto do Desarmamento) e decretos regulamentadores para aquisição de arma de fogo.</p>

<div style="margin-top: 50px; text-align: center;">
    Teresina, {{ data_hoje }}
    <br><br><br>
    _____________________________________<br>
    <b>{{ empresa.razao_social }}</b><br>VENDEDOR
    <br><br><br>
    _____________________________________<br>
    <b>{{ cliente.nome }}</b><br>COMPRADOR
</div>
"""

# ==============================================================================
# 4. CONTRATO DE DESPACHANTE
# ==============================================================================
SERVICO_DESPACHANTE = """
<style>
    body { font-family: Arial, sans-serif; font-size: 12px; }
    .header { text-align: center; font-weight: bold; margin-bottom: 20px; border-bottom: 1px solid #ccc; padding-bottom: 10px; }
</style>

<div class="header">
    CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE ASSESSORIA DOCUMENTAL
</div>

<p><b>CONTRATADO:</b> MAURICIO BATISTA DE SOUSA, despachante documentalista, endereço profissional na {{ empresa.endereco }}.</p>

<p><b>CONTRATANTE:</b> {{ cliente.nome }}, CPF {{ cliente.documento }}, residente em {{ cliente.endereco_completo }}.</p>

<p><b>1. OBJETO:</b> O presente contrato tem por objeto a prestação de serviços de assessoria para instrução e protocolo de processos administrativos junto ao Exército Brasileiro (SFPC) ou Polícia Federal (SINARM), visando a concessão de CR, aquisição, renovação ou transferência de arma de fogo.</p>

<p><b>2. VALOR:</b> Pelos serviços prestados, o Contratante pagará o valor de <b>{{ br_money(venda.valor_total) }}</b>.</p>

<p><b>3. OBRIGAÇÕES:</b> O Contratado compromete-se a realizar o serviço com zelo e técnica. O Contratante responsabiliza-se pela veracidade dos documentos e informações fornecidas.</p>

<p><b>4. RESULTADO:</b> A obrigação do Contratado é de meio, não de fim. O deferimento do processo é ato discricionário da administração pública.</p>

<div style="margin-top: 50px; text-align: center;">
    Teresina, {{ data_hoje }}
    <br><br>
    __________________________________<br>
    CONTRATANTE
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

        print("🔄 Atualizando modelos de documentos (Layout Tiro Digital)...")
        for d in dados:
            modelo = ModeloDocumento.query.filter_by(chave=d['chave']).first()
            if modelo:
                modelo.conteudo = d['conteudo']
                modelo.titulo = d['titulo']
                print(f"✏️  Atualizado: {d['titulo']}")
            else:
                m = ModeloDocumento(**d)
                db.session.add(m)
                print(f"➕ Criado: {d['titulo']}")
        
        db.session.commit()
        print("✅ Modelos sincronizados com sucesso!")

if __name__ == "__main__":
    seed()