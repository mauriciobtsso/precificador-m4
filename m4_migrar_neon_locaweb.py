#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Migração Neon -> Locaweb (v2)
- .env: DATABASE_URL_NEON, DATABASE_URL_LOCAWEB
- Interseção de colunas; não sobrescreve destino
- Dedup por chaves de negócio (clientes: cpf_cnpj; produtos: codigo/sku)
- Conversão Latin-1 -> UTF-8 para strings
- Defaults automáticos (created_at/updated_at/criado_em/atualizado_em; booleans False)
- Ordem hierárquica e validação de FKs (pula órfãos)
- ON CONFLICT DO NOTHING quando PK/UNIQUE disponível
- Logs em migration_logs/<timestamp>/
"""

import os
import csv
import sys
import json
import datetime
import decimal
from collections import defaultdict, deque

from dotenv import load_dotenv
from tqdm import tqdm

from sqlalchemy import create_engine, MetaData, Table, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import types as satypes
from sqlalchemy.dialects.postgresql import insert as pg_insert

# =======================
# Config
# =======================
BATCH_SIZE = 1000
LOG_DIR_BASE = "migration_logs"

CLIENTES_TABLE_HINTS = {"clientes", "cliente"}
PRODUTOS_TABLE_HINTS = {"produtos", "produto"}

CLIENTES_KEY_CANDIDATES = ["cpf_cnpj", "cpfcnpj", "documento", "cpf", "cnpj"]
PRODUTOS_KEY_CANDIDATES = ["codigo", "sku", "codigo_sku", "cod_sku"]

# Prioridade opcional (pais -> filhos). FKs do destino também são consideradas.
MANUAL_PRIORITY = [
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
    "pedido_compra",
    "item_pedido",
    "notificacao",
    "comunicacoes",
]

# =======================
# Utils
# =======================
def now_tag():
    return datetime.datetime.now().strftime("%Y-%m-%d_%H%M")

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def write_csv(path: str, rows: list, header: list = None):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if header:
            w.writerow(header)
        for r in rows:
            w.writerow(r)

def safe_json_dumps(obj):
    def default(o):
        if isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat()
        if isinstance(o, decimal.Decimal):
            return float(o)
        return str(o)
    return json.dumps(obj, ensure_ascii=False, default=default)

def sanitize_text(v):
    # Corrige textos vindos com "Ã©/Ã§/Ãº" etc.
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except Exception:
            try:
                return v.decode("latin-1")
            except Exception:
                return v.decode("utf-8", errors="ignore")
    if isinstance(v, str):
        try:
            return v.encode("latin1").decode("utf-8")
        except Exception:
            return v
    return v

def normalize_digits_only(v):
    if not v:
        return v
    s = "".join(ch for ch in str(v) if ch.isdigit())
    return s or None

def normalize_code(v):
    if v is None:
        return None
    return str(v).strip().upper()

def load_env_or_die():
    load_dotenv()
    url_src = os.getenv("DATABASE_URL_NEON")
    url_dst = os.getenv("DATABASE_URL_LOCAWEB")
    if not url_src or not url_dst:
        print("ERRO: defina DATABASE_URL_NEON e DATABASE_URL_LOCAWEB no .env", file=sys.stderr)
        sys.exit(1)
    return url_src, url_dst

def create_engines():
    url_src, url_dst = load_env_or_die()
    eng_src = create_engine(url_src)
    eng_dst = create_engine(url_dst)
    return eng_src, eng_dst

def reflect_metadata(engine: Engine):
    meta = MetaData()
    meta.reflect(bind=engine)
    return meta

def common_tables(meta_src: MetaData, meta_dst: MetaData):
    src_names = set(meta_src.tables.keys())
    dst_names = set(meta_dst.tables.keys())
    common = sorted(src_names.intersection(dst_names))
    return common

def table_hint(name: str, hints: set):
    n = name.lower()
    return any(h in n for h in hints)

def intersect_columns(tbl_src: Table, tbl_dst: Table):
    src_cols = set(c.name for c in tbl_src.columns)
    dst_cols = set(c.name for c in tbl_dst.columns)
    inter = sorted(src_cols.intersection(dst_cols))
    return inter

def is_bool_col(col):
    return isinstance(col.type, satypes.Boolean)

def is_textual_col(col):
    return isinstance(col.type, (satypes.String, satypes.Text, satypes.Unicode, satypes.UnicodeText))

def is_datetime_col(col):
    return isinstance(col.type, (satypes.DateTime, satypes.Date, satypes.TIMESTAMP, satypes.TIME))

def is_numeric_col(col):
    return isinstance(col.type, (satypes.Numeric, satypes.Integer, satypes.BigInteger, satypes.Float))

def build_order_by_fk(meta_dst: MetaData, tables: list):
    # Grafo por FKs do destino
    graph = defaultdict(set)
    indeg = {t: 0 for t in tables}
    for t in tables:
        tbl = meta_dst.tables[t]
        for fk in tbl.foreign_key_constraints:
            parents = {elem.column.table.name for elem in fk.elements}
            for p in parents:
                if p in indeg and p != t and t not in graph[p]:
                    graph[p].add(t)
                    indeg[t] += 1
    # Kahn
    q = deque([t for t in tables if indeg[t] == 0])
    topo = []
    while q:
        u = q.popleft()
        topo.append(u)
        for v in graph.get(u, []):
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    if len(topo) != len(tables):
        # ciclo → usa ordem original
        topo = tables[:]
    # Reforça prioridade manual quando existir
    prio = {name: i for i, name in enumerate(MANUAL_PRIORITY)}
    topo.sort(key=lambda x: prio.get(x, 9999))
    return topo

def find_business_key_columns(table_name: str, cols: list):
    # clientes
    if table_hint(table_name, CLIENTES_TABLE_HINTS):
        lower = [c.lower() for c in cols]
        for c in CLIENTES_KEY_CANDIDATES:
            if c in lower:
                return [cols[lower.index(c)]], "clientes"
    # produtos
    if table_hint(table_name, PRODUTOS_TABLE_HINTS):
        lower = [c.lower() for c in cols]
        for c in PRODUTOS_KEY_CANDIDATES:
            if c in lower:
                return [cols[lower.index(c)]], "produtos"
    return None, None

def find_pk_or_unique_keys(tbl: Table):
    if tbl.primary_key and tbl.primary_key.columns:
        return [c.name for c in tbl.primary_key.columns], "pk"
    for cons in tbl.constraints:
        if isinstance(cons, UniqueConstraint) and cons.columns:
            return [c.name for c in cons.columns], "unique"
    return None, None

def build_identifier_key(row: dict, key_cols: list, table_kind: str | None):
    key_vals = []
    for c in key_cols:
        v = row.get(c)
        if isinstance(v, str):
            v = v.strip()
        key_vals.append(v)
    # normalizações por negócio
    if table_kind == "clientes":
        # normaliza CPF/CNPJ/documento para só dígitos
        key_vals = [normalize_digits_only(v) for v in key_vals]
    elif table_kind == "produtos":
        # normaliza codigo/sku para UPPER sem espaços
        key_vals = [normalize_code(v) for v in key_vals]
    return tuple(key_vals)

def preload_existing_keys(engine: Engine, tbl: Table, key_cols: list, table_kind: str | None):
    existing = set()
    cols = [tbl.c[c] for c in key_cols if c in tbl.c]
    if not cols:
        return existing
    try:
        with engine.connect() as conn:
            offset = 0
            limit = 50000
            while True:
                stmt = select(*cols).limit(limit).offset(offset)
                res = conn.execute(stmt)
                rows = res.fetchall()
                if not rows:
                    break
                for r in rows:
                    row_tuple = tuple(r)
                    # aplica normalizações na chave existente do destino
                    norm = []
                    for i, val in enumerate(row_tuple):
                        if table_kind == "clientes":
                            norm.append(normalize_digits_only(val))
                        elif table_kind == "produtos":
                            norm.append(normalize_code(val))
                        else:
                            norm.append(val)
                    existing.add(tuple(norm))
                if len(rows) < limit:
                    break
                offset += limit
    except SQLAlchemyError as e:
        print(f"[WARN] Falha ao pré-carregar chaves de {tbl.name}: {e}")
    return existing

def preload_fk_sets(engine: Engine, meta: MetaData, table_name: str):
    """
    Para cada FK de table_name no destino, carrega o conjunto de valores existentes
    do lado referenciado (tipicamente 'id').
    Retorna dict { (ref_table, ref_column) : set(...) }
    """
    tbl = meta.tables[table_name]
    fk_sets = {}
    with engine.connect() as conn:
        for fk in tbl.foreign_key_constraints:
            for elem in fk.elements:
                ref_tbl = elem.column.table
                ref_col = elem.column
                key = (ref_tbl.name, ref_col.name)
                if key in fk_sets:
                    continue
                try:
                    # coleta todos IDs do pai
                    vals = set()
                    offset = 0
                    limit = 50000
                    while True:
                        stmt = select(ref_col).select_from(ref_tbl).limit(limit).offset(offset)
                        rs = conn.execute(stmt).fetchall()
                        if not rs:
                            break
                        for r in rs:
                            vals.add(r[0])
                        if len(rs) < limit:
                            break
                        offset += limit
                    fk_sets[key] = vals
                except SQLAlchemyError as e:
                    print(f"[WARN] Falha ao carregar FK set {ref_tbl.name}.{ref_col.name}: {e}")
    return fk_sets

def fill_defaults(row: dict, tbl_dst: Table):
    # timestamps
    now = datetime.datetime.now()
    for k in ("created_at", "updated_at", "criado_em", "atualizado_em"):
        if k in row and (row[k] is None or row[k] == ""):
            row[k] = now
    # booleans -> False se None
    for c in tbl_dst.columns:
        if is_bool_col(c) and c.name in row and row[c.name] is None:
            row[c.name] = False
    return row

def sanitize_row_texts(row: dict, tbl_dst: Table):
    # aplica normalização de texto apenas em colunas textuais
    for c in tbl_dst.columns:
        name = c.name
        if name in row and is_textual_col(c) and isinstance(row[name], (str, bytes)):
            row[name] = sanitize_text(row[name])
    return row

def source_count(engine: Engine, table_name: str) -> int:
    try:
        with engine.connect() as c:
            return c.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar() or 0
    except SQLAlchemyError:
        return 0

def fetch_source_rows(engine: Engine, tbl: Table, cols: list, offset: int, limit: int):
    with engine.connect() as conn:
        stmt = select(*[tbl.c[c] for c in cols]).limit(limit).offset(offset)
        res = conn.execute(stmt)
        return [dict(r._mapping) for r in res.fetchall()]

def insert_rows(engine: Engine, tbl: Table, rows: list, key_cols: list | None):
    if not rows:
        return 0
    # Usa ON CONFLICT DO NOTHING quando possível (quando existe PK/UNIQUE)
    try:
        if key_cols:
            stmt = pg_insert(tbl).values(rows).on_conflict_do_nothing()
            with engine.begin() as conn:
                conn.execute(stmt)
            return len(rows)  # as linhas "conflitadas" não contam erro
    except Exception:
        pass
    # fallback
    try:
        with engine.begin() as conn:
            conn.execute(tbl.insert(), rows)
        return len(rows)
    except IntegrityError:
        successes = 0
        with engine.begin() as conn:
            for r in rows:
                try:
                    conn.execute(tbl.insert().values(**r))
                    successes += 1
                except IntegrityError:
                    continue
        return successes

# =======================
# Main pipeline
# =======================
def main():
    print(">> Iniciando migração Neon → Locaweb (v2)")
    eng_src, eng_dst = create_engines()

    print(">> Refletindo metadados...")
    meta_src = reflect_metadata(eng_src)
    meta_dst = reflect_metadata(eng_dst)

    tables = common_tables(meta_src, meta_dst)
    if not tables:
        print("Nenhuma tabela em comum.")
        return

    # Ordena por FKs + prioridade manual
    ordered = build_order_by_fk(meta_dst, tables)

    stamp = now_tag()
    log_dir = os.path.join(LOG_DIR_BASE, stamp)
    ensure_dir(log_dir)
    summary_rows = []
    summary_header = ["tabela", "linhas_origem", "inseridos", "ignorados", "erros", "chave_usada", "colunas_usadas"]

    for tname in ordered:
        tbl_src = meta_src.tables[tname]
        tbl_dst = meta_dst.tables[tname]
        use_cols = intersect_columns(tbl_src, tbl_dst)
        if not use_cols:
            summary_rows.append([tname, 0, 0, 0, 0, "", ""])
            continue

        # Descobrir chave (negócio > PK/UNIQUE > all_columns)
        biz_cols, table_kind = find_business_key_columns(tname, use_cols)
        key_cols = None
        key_kind = ""
        if biz_cols:
            key_cols = biz_cols
            key_kind = f"business:{'+'.join(key_cols)}"
        else:
            key_cols, uniq_kind = find_pk_or_unique_keys(tbl_dst)
            if key_cols:
                key_kind = f"{uniq_kind}:{'+'.join(key_cols)}"
            else:
                key_cols = use_cols[:]  # fallback pesado
                key_kind = "all_columns"

        existing_keys = preload_existing_keys(eng_dst, tbl_dst, key_cols, table_kind)

        # Prepara FK sets para validação
        fk_required_sets = preload_fk_sets(eng_dst, meta_dst, tname)

        total_src = total_inserted = total_skipped = total_errors = 0
        skipped_rows_log, errors_rows_log = [], []

        print(f"\n[Tabela {tname}] Colunas: {len(use_cols)} | Chave: {key_kind}")
        total_count = source_count(eng_src, tname)
        pbar = tqdm(total=total_count, desc=f"{tname}", unit="row")

        offset = 0
        while True:
            batch = fetch_source_rows(eng_src, tbl_src, use_cols, offset, BATCH_SIZE)
            if not batch:
                break
            total_src += len(batch)

            to_insert = []
            for raw in batch:
                try:
                    row = dict(raw)

                    # Normalização de textos (corrige acentos quebrados)
                    row = sanitize_row_texts(row, tbl_dst)

                    # Defaults automáticos (timestamps + booleans False)
                    row = fill_defaults(row, tbl_dst)

                    # Ajustes específicos de negócio para chaves
                    if table_kind == "clientes":
                        # garantir cpf_cnpj: preferir cpf_cnpj/documento; normalizar dígitos
                        for cand in CLIENTES_KEY_CANDIDATES:
                            if cand in row and row[cand]:
                                row[cand] = normalize_digits_only(row[cand])
                        if "cpf_cnpj" in row and not row["cpf_cnpj"]:
                            row["cpf_cnpj"] = normalize_digits_only(row.get("documento"))

                    if table_hint(tname, PRODUTOS_TABLE_HINTS):
                        # normalizar codigo/sku
                        for cand in PRODUTOS_KEY_CANDIDATES:
                            if cand in row and row[cand]:
                                row[cand] = normalize_code(row[cand])

                    # Dedup
                    ident = build_identifier_key(row, key_cols, table_kind)
                    if ident in existing_keys:
                        total_skipped += 1
                        if len(skipped_rows_log) < 2000:
                            skipped_rows_log.append([safe_json_dumps(row)])
                        continue

                    # Validação genérica de FKs: se houver, exige presença no destino
                    fk_ok = True
                    for fk in tbl_dst.foreign_key_constraints:
                        for elem in fk.elements:
                            local_col = elem.parent.name
                            ref_tbl = elem.column.table.name
                            ref_col = elem.column.name
                            key = (ref_tbl, ref_col)
                            if local_col in row and row[local_col] is not None:
                                ref_set = fk_required_sets.get(key)
                                if ref_set is not None and row[local_col] not in ref_set:
                                    fk_ok = False
                                    break
                        if not fk_ok:
                            break
                    if not fk_ok:
                        total_errors += 1
                        if len(errors_rows_log) < 2000:
                            errors_rows_log.append(
                                ["fk_missing", safe_json_dumps(row)]
                            )
                        continue

                    to_insert.append(row)

                except Exception as e:
                    total_errors += 1
                    if len(errors_rows_log) < 2000:
                        errors_rows_log.append([str(e), safe_json_dumps(raw)])
                    continue

            try:
                inserted = insert_rows(eng_dst, tbl_dst, to_insert, key_cols if key_kind != "all_columns" else None)
                total_inserted += inserted
                # atualiza cache de chaves
                for r in to_insert[:inserted]:
                    ident2 = build_identifier_key(r, key_cols, table_kind)
                    existing_keys.add(ident2)
                # se a tabela recém-inserida for pai de outras, atualizar sets de FKs locais
                # (atualiza os sets que apontam para ela mesma)
                for fk in tbl_dst.foreign_key_constraints:
                    for elem in fk.elements:
                        # caso raro de self-ref
                        pass
            except Exception as e:
                total_errors += len(to_insert)
                if len(errors_rows_log) < 2000:
                    errors_rows_log.append([f"batch_error:{str(e)}", f"batch_size={len(to_insert)}"])

            offset += BATCH_SIZE
            pbar.update(len(batch))

        pbar.close()

        if skipped_rows_log:
            write_csv(os.path.join(log_dir, f"skipped_{tname}.csv"), skipped_rows_log, header=["row_json"])
        if errors_rows_log:
            write_csv(os.path.join(log_dir, f"errors_{tname}.csv"), errors_rows_log, header=["error", "row_json"])

        summary_rows.append([
            tname,
            total_src,
            total_inserted,
            total_skipped,
            total_errors,
            key_kind,
            ",".join(use_cols)
        ])

        print(f"[Resumo {tname}] origem={total_src} | inseridos={total_inserted} | ignorados={total_skipped} | erros={total_errors}")

    write_csv(os.path.join(log_dir, "summary.csv"), summary_rows, header=summary_header)
    print(f"\n✅ Migração concluída (v2). Logs em: {log_dir}")
    print("Resumo:", os.path.join(log_dir, "summary.csv"))

if __name__ == "__main__":
    main()
