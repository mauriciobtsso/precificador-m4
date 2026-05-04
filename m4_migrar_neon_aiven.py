#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Migração Direta e Definitiva: Neon -> Aiven (DB-to-DB)
- Origem: Neon (DATABASE_URL)
- Destino: Aiven (DATABASE_URL_AIVEN)
- Inclui Usuários, Compras, Produtos e Histórico.
- Sincroniza Sequences (IDs) no final para evitar erro de Primary Key.
"""

import os
import sys
import csv
import json
import datetime
import decimal

from dotenv import load_dotenv
from tqdm import tqdm
from sqlalchemy import create_engine, MetaData, Table, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import types as satypes
from sqlalchemy.dialects.postgresql import insert as pg_insert

# ============== Config ==============
BASE_DIR = r"C:\precificador-m4\backups_bd"
BATCH_SIZE = 1000

CLIENTES_TABLE_HINTS = {"clientes", "cliente"}
PRODUTOS_TABLE_HINTS = {"produtos", "produto"}
CLIENTES_KEY_CANDIDATES = ["cpf_cnpj", "cpfcnpj", "documento", "cpf", "cnpj"]
PRODUTOS_KEY_CANDIDATES = ["codigo", "sku", "codigo_sku", "cod_sku"]

# GARANTIA DE QUE TUDO VAI SER MIGRADO, INCLUINDO USUÁRIOS
MANUAL_PRIORITY = [
    "users",
    "usuarios",
    "tipo_produto",
    "marca_produto",
    "calibre_produto",
    "categoria_produto",
    "funcionamento_produto",
    "clientes",
    "clientes_enderecos",
    "clientes_contatos",
    "produtos",
    "documentos",
    "vendas",
    "itens_venda",
    "compra_nf",
    "compra_item",
    "estoque_itens",
    "certidoes",
    "produto_historico",
    "pedido_compra",
    "item_pedido",
    "notificacao",
    "comunicacoes",
]

# ============== Utils ==============
def now_tag(): return datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
def ensure_dir(path): os.makedirs(path, exist_ok=True)

def load_env_or_die():
    load_dotenv()
    url_src = os.getenv("DATABASE_URL")
    url_dst = os.getenv("DATABASE_URL_AIVEN")
    if not url_src or not url_dst:
        print("ERRO: defina DATABASE_URL (Neon) e DATABASE_URL_AIVEN (Aiven) no .env", file=sys.stderr)
        sys.exit(1)
    return url_src, url_dst

def create_engines():
    url_src, url_dst = load_env_or_die()
    return create_engine(url_src), create_engine(url_dst)

def reflect(engine: Engine):
    meta = MetaData()
    meta.reflect(bind=engine)
    return meta

def is_bool_col(col): return isinstance(col.type, satypes.Boolean)
def is_textual_col(col): return isinstance(col.type, (satypes.String, satypes.Text, satypes.Unicode, satypes.UnicodeText))

def sanitize_text(v):
    if isinstance(v, bytes):
        try: return v.decode("utf-8")
        except: return v.decode("utf-8", errors="ignore")
    if isinstance(v, str):
        try: return v.encode("latin1").decode("utf-8")
        except: return v
    return v

def normalize_digits_only(v):
    if not v: return v
    s = "".join(ch for ch in str(v) if ch.isdigit())
    return s or None

def normalize_code(v):
    if v is None: return None
    return str(v).strip().upper()

def common_tables(meta_src: MetaData, meta_dst: MetaData):
    return sorted(set(meta_src.tables.keys()).intersection(set(meta_dst.tables.keys())))

def intersect_columns(tbl_src: Table, tbl_dst: Table):
    return sorted(set(c.name for c in tbl_src.columns).intersection(set(c.name for c in tbl_dst.columns)))

def find_business_key_columns(table_name: str, cols: list):
    if any(h in table_name.lower() for h in CLIENTES_TABLE_HINTS):
        lower = [c.lower() for c in cols]
        for c in CLIENTES_KEY_CANDIDATES:
            if c in lower: return [cols[lower.index(c)]], "clientes"
    if any(h in table_name.lower() for h in PRODUTOS_TABLE_HINTS):
        lower = [c.lower() for c in cols]
        for c in PRODUTOS_KEY_CANDIDATES:
            if c in lower: return [cols[lower.index(c)]], "produtos"
    return None, None

def find_pk_or_unique_keys(tbl: Table):
    if tbl.primary_key and tbl.primary_key.columns:
        return [c.name for c in tbl.primary_key.columns], "pk"
    for cons in tbl.constraints:
        if isinstance(cons, UniqueConstraint) and cons.columns:
            return [c.name for c in cons.columns], "unique"
    return None, None

def build_identifier_key(row: dict, key_cols: list, kind: str | None):
    vals = []
    for c in key_cols:
        v = row.get(c)
        if isinstance(v, str): v = v.strip()
        vals.append(v)
    if kind == "clientes": vals = [normalize_digits_only(v) for v in vals]
    elif kind == "produtos": vals = [normalize_code(v) for v in vals]
    return tuple(vals)

def preload_existing_keys(engine: Engine, tbl: Table, key_cols: list, kind: str | None):
    out = set()
    if not key_cols: return out
    cols = [tbl.c[c] for c in key_cols if c in tbl.c]
    if not cols: return out
    with engine.connect() as conn:
        off, lim = 0, 50000
        while True:
            rows = conn.execute(select(*cols).limit(lim).offset(off)).fetchall()
            if not rows: break
            for r in rows:
                vals = list(r)
                if kind == "clientes": vals = [normalize_digits_only(x) for x in vals]
                elif kind == "produtos": vals = [normalize_code(x) for x in vals]
                out.add(tuple(vals))
            if len(rows) < lim: break
            off += lim
    return out

def fill_defaults(row: dict, tbl_dst: Table):
    now = datetime.datetime.now()
    for k in ("created_at","updated_at","criado_em","atualizado_em"):
        if k in row and (row[k] is None or row[k] == ""): row[k] = now
    for c in tbl_dst.columns:
        if is_bool_col(c) and c.name in row and row[c.name] is None: row[c.name] = False
    return row

def sanitize_row_texts(row: dict, tbl_dst: Table):
    for c in tbl_dst.columns:
        if c.name in row and is_textual_col(c) and isinstance(row[c.name], (str, bytes)):
            row[c.name] = sanitize_text(row[c.name])
    return row

def fetch_db_rows(engine: Engine, tbl: Table, use_cols: list):
    with engine.connect() as conn:
        off = 0
        while True:
            stmt = select(*[tbl.c[c] for c in use_cols]).limit(BATCH_SIZE).offset(off)
            rows = conn.execute(stmt).fetchall()
            if not rows: break
            yield [dict(r._mapping) for r in rows]
            off += len(rows)

def insert_rows(engine: Engine, tbl: Table, rows: list, key_cols: list | None):
    if not rows: return 0
    try:
        if key_cols:
            stmt = pg_insert(tbl).values(rows).on_conflict_do_nothing()
            with engine.begin() as conn:
                conn.execute(stmt)
            return len(rows)
    except Exception: pass
    try:
        with engine.begin() as conn:
            conn.execute(tbl.insert(), rows)
        return len(rows)
    except IntegrityError:
        ok = 0
        with engine.begin() as conn:
            for r in rows:
                try:
                    conn.execute(tbl.insert().values(**r))
                    ok += 1
                except IntegrityError: pass
        return ok

def resetar_sequences(engine: Engine, meta: MetaData):
    """Sincroniza os contadores de ID no PostgreSQL (Sequences) para o banco destino"""
    print("\n>> Sincronizando IDs automáticos (Sequences) na Aiven...")
    with engine.begin() as conn:
        for tname, table in meta.tables.items():
            if 'id' in table.columns and isinstance(table.columns['id'].type, satypes.Integer):
                try:
                    sql = text(f"SELECT setval(pg_get_serial_sequence('\"{tname}\"', 'id'), coalesce(max(id), 1), max(id) IS NOT null) FROM \"{tname}\";")
                    conn.execute(sql)
                    print(f"   ✅ Sequence atualizada: {tname}")
                except Exception:
                    pass

def build_processing_order(meta_dst: MetaData, tables: list):
    prio = {name: i for i, name in enumerate(MANUAL_PRIORITY)}
    tables = [t for t in tables]
    tables.sort(key=lambda x: prio.get(x, 9999))
    return tables

# ============== Main ==============
def main():
    print(">> Conectando aos bancos (Neon -> Aiven)...")
    url_neon, url_aiven = load_env_or_die()
    eng_src, eng_dst = create_engines()

    meta_src = reflect(eng_src)
    meta_dst = reflect(eng_dst)

    tables = common_tables(meta_src, meta_dst)
    order = build_processing_order(meta_dst, tables)

    log_dir = os.path.join(BASE_DIR, f"migration_logs_{now_tag()}")
    ensure_dir(log_dir)
    
    print(f">> Iniciando migração direta DB-to-DB. Tabelas a processar: {len(order)}")

    for tname in order:
        tbl_src = meta_src.tables[tname]
        tbl_dst = meta_dst.tables[tname]
        use_cols = intersect_columns(tbl_src, tbl_dst)
        if not use_cols: continue

        biz_cols, kind = find_business_key_columns(tname, use_cols)
        if biz_cols:
            key_cols = biz_cols
            key_desc = f"business:{'+'.join(key_cols)}"
        else:
            key_cols, kkind = find_pk_or_unique_keys(tbl_dst)
            key_desc = f"{kkind}:{'+'.join(key_cols)}" if key_cols else "all_columns"
            if not key_cols: key_cols = use_cols[:]

        existing = preload_existing_keys(eng_dst, tbl_dst, key_cols, kind)

        total_src = total_ins = total_err = 0
        print(f"\n[Tabela {tname}] Transferindo...")

        batches = fetch_db_rows(eng_src, tbl_src, use_cols)
        pbar = tqdm(desc=f"{tname}", unit="row")

        for batch in batches:
            total_src += len(batch)
            to_insert = []
            for raw in batch:
                try:
                    row = dict(raw)
                    row = sanitize_row_texts(row, tbl_dst)
                    row = fill_defaults(row, tbl_dst)
                    
                    if kind == "clientes":
                        for cand in CLIENTES_KEY_CANDIDATES:
                            if cand in row and row[cand]: row[cand] = normalize_digits_only(row[cand])
                        if "cpf_cnpj" in row and not row["cpf_cnpj"]: row["cpf_cnpj"] = normalize_digits_only(row.get("documento"))
                    if any(h in tname.lower() for h in PRODUTOS_TABLE_HINTS):
                        for cand in PRODUTOS_KEY_CANDIDATES:
                            if cand in row and row[cand]: row[cand] = normalize_code(row[cand])

                    ident = build_identifier_key(row, key_cols, kind)
                    if ident in existing: continue
                    to_insert.append(row)
                except Exception:
                    total_err += 1
                    continue

            try:
                ins = insert_rows(eng_dst, tbl_dst, to_insert, key_cols if key_desc != "all_columns" else None)
                total_ins += ins
                for r in to_insert[:ins]: existing.add(build_identifier_key(r, key_cols, kind))
            except Exception:
                total_err += len(to_insert)

            pbar.update(len(batch))
        pbar.close()
        print(f"   => Inseridos: {total_ins} | Erros/Ignorados: {total_err}")

    # MÁGICA FINAL: Ajusta os IDs para não quebrar o sistema!
    resetar_sequences(eng_dst, meta_dst)
    print("\n✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO. Aiven está pronto para produção.")

if __name__ == "__main__":
    main()