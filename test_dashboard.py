from app import create_app, db
from app.clientes.models import Cliente
from datetime import datetime

app = create_app()
app.app_context().push()

clientes = Cliente.query.all()

if not clientes:
    print("⚠️ Nenhum cliente encontrado.")
else:
    for cliente in clientes:
        print("="*50)
        print(f"Cliente #{cliente.id}: {cliente.nome}")

        # Resumo
        resumo = {
            "documentos": len(cliente.documentos),
            "armas": len(cliente.armas),
            "comunicacoes": len(cliente.comunicacoes),
            "processos": len(cliente.processos),
            "vendas": len(cliente.vendas)
        }
        print("\nResumo:", resumo)

        # Alertas
        alertas = []
        if not cliente.cr or not cliente.cr_emissor:
            alertas.append("CR não informado.")
        if cliente.data_validade_cr and cliente.data_validade_cr < datetime.now().date():
            alertas.append(f"CR vencido em {cliente.data_validade_cr.strftime('%d/%m/%Y')}")
        for doc in cliente.documentos:
            if doc.validade and doc.validade < datetime.now().date():
                alertas.append(f"Documento '{doc.tipo}' vencido em {doc.validade.strftime('%d/%m/%Y')}")
        for proc in cliente.processos:
            if proc.status and proc.status.lower() not in ["concluido", "finalizado"]:
                alertas.append(f"Processo em andamento: {proc.tipo} ({proc.status})")

        print("\nAlertas:", alertas if alertas else "Nenhum alerta")

        # Timeline
        eventos = []
        if cliente.vendas:
            ultima_venda = max(cliente.vendas, key=lambda v: v.data_abertura or v.data_fechamento or v.created_at)
            eventos.append({"data": ultima_venda.data_abertura or ultima_venda.created_at, "tipo": "Venda", "descricao": f"Venda #{ultima_venda.id}"})

        if cliente.comunicacoes:
            ultima_com = max(cliente.comunicacoes, key=lambda c: c.data)
            eventos.append({"data": ultima_com.data, "tipo": "Comunicação", "descricao": (ultima_com.assunto or ultima_com.mensagem[:30])})

        if cliente.documentos:
            ultimo_doc = max(cliente.documentos, key=lambda d: d.data_upload)
            eventos.append({"data": ultimo_doc.data_upload, "tipo": "Documento", "descricao": ultimo_doc.tipo})

        if cliente.processos:
            ultimo_proc = max(cliente.processos, key=lambda p: p.data)
            eventos.append({"data": ultimo_proc.data, "tipo": "Processo", "descricao": ultimo_proc.descricao or ultimo_proc.tipo})

        timeline = sorted(eventos, key=lambda e: e["data"], reverse=True)[:5]

        print("\nTimeline:")
        if timeline:
            for e in timeline:
                print(f"- {e['data']} | {e['tipo']} — {e['descricao']}")
        else:
            print("Nenhum evento recente.")
        print("="*50 + "\n")
