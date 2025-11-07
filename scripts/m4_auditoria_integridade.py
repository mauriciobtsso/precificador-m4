# -*- coding: utf-8 -*-
# ============================================================
# SCRIPT: m4_auditoria_integridade.py
# OBJETIVO: Auditoria de integridade do banco de dados M4
# FASE: Etapa 4 — Campos críticos + Relatório CSV
# ============================================================

import os
import csv
from datetime import datetime
from colorama import Fore, Style, init
from app import db
from app.clientes.models import Cliente
from app.produtos.models import Produto
from app.models import Venda, ItemVenda, PedidoCompra, ItemPedido

# Inicializa colorama (cores no console)
init(autoreset=True)

print(f"{Fore.CYAN}[M4] Iniciando auditoria de integridade — Etapa 4{Style.RESET_ALL}")

try:
    # ============================================================
    # ETAPA 1 — Teste de conexão
    # ============================================================
    with db.engine.connect() as conn:
        result = conn.execute(db.text("SELECT NOW()"))
        data = result.scalar()
        print(f"{Fore.GREEN}Conexão OK com o banco — {data}{Style.RESET_ALL}")

    # ============================================================
    # ETAPA 2 — Contagens básicas
    # ============================================================
    def contar(model, nome):
        try:
            qtd = db.session.query(model).count()
            cor = Fore.GREEN if qtd > 0 else Fore.RED
            print(f"{cor}{nome:<20}: {qtd:>6} registro(s){Style.RESET_ALL}")
            return qtd
        except Exception as e:
            print(f"{Fore.RED}[ERRO] Falha ao contar {nome}: {e}{Style.RESET_ALL}")
            return None

    print(f"\n{Fore.CYAN}==> Contagem de registros principais{Style.RESET_ALL}")
    qtd_clientes = contar(Cliente, "Clientes")
    qtd_produtos = contar(Produto, "Produtos")
    qtd_vendas = contar(Venda, "Vendas")
    qtd_itens_venda = contar(ItemVenda, "Itens de Venda")
    qtd_pedidos = contar(PedidoCompra, "Pedidos de Compra")
    qtd_itens_pedido = contar(ItemPedido, "Itens de Pedido")

    # ============================================================
    # ETAPA 3 — Verificação de FKs
    # ============================================================
    print(f"\n{Fore.CYAN}==> Verificação de chaves estrangeiras (FKs){Style.RESET_ALL}")

    def verificar_fk(model, campo_fk, tabela_destino, campo_destino, nome_relacao):
        try:
            sql_nulos = db.text(f"SELECT COUNT(*) FROM {model.__tablename__} WHERE {campo_fk} IS NULL")
            sql_invalidos = db.text(
                f"SELECT COUNT(*) FROM {model.__tablename__} "
                f"WHERE {campo_fk} IS NOT NULL AND {campo_fk} NOT IN "
                f"(SELECT {campo_destino} FROM {tabela_destino})"
            )
            nulos = db.session.execute(sql_nulos).scalar()
            invalidos = db.session.execute(sql_invalidos).scalar()

            if invalidos > 0:
                print(f"{Fore.RED}❌ {nome_relacao:<25}: {invalidos} FKs inválidas{Style.RESET_ALL}")
            elif nulos > 0:
                print(f"{Fore.YELLOW}⚠️  {nome_relacao:<25}: {nulos} FKs nulas{Style.RESET_ALL}")
            else:
                print(f"{Fore.GREEN}✓ {nome_relacao:<25}: OK{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}[ERRO] Falha ao verificar {nome_relacao}: {e}{Style.RESET_ALL}")

    verificar_fk(Venda, "cliente_id", "clientes", "id", "Venda → Cliente")
    verificar_fk(PedidoCompra, "fornecedor_id", "clientes", "id", "PedidoCompra → Fornecedor")
    verificar_fk(ItemVenda, "venda_id", "vendas", "id", "ItemVenda → Venda")
    verificar_fk(ItemPedido, "pedido_id", "pedido_compra", "id", "ItemPedido → PedidoCompra")

    # ============================================================
    # ETAPA 4 — Validação de campos críticos
    # ============================================================
    print(f"\n{Fore.CYAN}==> Validação de campos críticos{Style.RESET_ALL}")

    inconsistencias = []

    def checar_nulos(model, campos, nome_tabela):
        for campo in campos:
            sql = db.text(f"SELECT id FROM {model.__tablename__} WHERE {campo} IS NULL OR TRIM(CAST({campo} AS TEXT)) = ''")
            ids = [r[0] for r in db.session.execute(sql)]
            for i in ids:
                inconsistencias.append([nome_tabela, "Campo nulo", i, campo, "Valor ausente", "ERRO"])
        if len(ids) == 0:
            print(f"{Fore.GREEN}✓ {nome_tabela:<20}: OK{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}⚠️  {nome_tabela:<20}: {len(ids)} campos nulos encontrados{Style.RESET_ALL}")

    checar_nulos(Produto, ["nome", "codigo", "preco_fornecedor", "margem", "preco_final"], "Produto")
    checar_nulos(Cliente, ["nome", "documento"], "Cliente")
    checar_nulos(Venda, ["cliente_id", "valor_total"], "Venda")
    checar_nulos(ItemVenda, ["produto_nome", "quantidade", "valor_total"], "ItemVenda")
    checar_nulos(PedidoCompra, ["numero", "fornecedor_id"], "PedidoCompra")
    checar_nulos(ItemPedido, ["descricao", "quantidade", "valor_unitario"], "ItemPedido")

    # ============================================================
    # ETAPA 5 — Geração do relatório CSV
    # ============================================================
    if inconsistencias:
        os.makedirs("instance/exports", exist_ok=True)
        data_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        caminho_csv = f"instance/exports/auditoria_integridade_{data_str}.csv"

        with open(caminho_csv, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile, delimiter=";")
            writer.writerow(["tabela", "tipo", "registro_id", "campo", "detalhe", "status"])
            writer.writerows(inconsistencias)

        print(f"\n{Fore.YELLOW}⚠️  Inconsistências encontradas: {len(inconsistencias)}")
        print(f"Relatório salvo em: {caminho_csv}{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.GREEN}✓ Nenhuma inconsistência de campo encontrada. Tudo OK!{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}[M4] Etapa 4 concluída com sucesso. Auditoria completa.{Style.RESET_ALL}")

except Exception as e:
    print(f"{Fore.RED}[ERRO] Falha geral na auditoria: {e}{Style.RESET_ALL}")
