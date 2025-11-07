#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Migração Neon -> Locaweb (v3, offline preferencial com fallback)
- Procura ZIP mais recente em C:\precificador-m4\backups_bd\exports_neon_*.zip
- Para cada tabela:
    1) tenta ler do ZIP (CSV UTF-8)
    2) se não existir no ZIP, lê da Neon (fallback)
- NÃO sobrescreve dados do destino (dedup por chave)
- Normaliza textos, preenche defaults (timestamps/booleans)
- Ordem hierárquica
- Criação automática de pais ausentes de PRODUTOS (marca/tipo/calibre/categoria)
- Suporte --only tabela1,tabela2
"""

import os
import sys
import csv
import json
import argparse
import zipfile
import datetime
import decimal
from io import TextIOWrapper

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

# ============== Utils ==============
def now_tag():
    return datetime.datetime.now().strftime("%Y-%m-%d_%H%M")

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

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
    return create_engine(url_src), create_engine(url_dst)

def reflect(engine: Engine):
    meta = MetaData()
    meta.reflect(bind=engine)
    return meta

def is_bool_col(col):     return isinstance(col.type, satypes.Boolean)
def is_textual_col(col):  return isinstance(col.type, (satypes.String, satypes.Text, satypes.Unicode, satypes.UnicodeText))

def sanitize_text(v):
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
    if kind == "clientes":
        vals = [normalize_digits_only(v) for v in vals]
    elif kind == "produtos":
        vals = [normalize_code(v) for v in vals]
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
                if kind == "clientes":
                    vals = [normalize_digits_only(x) for x in vals]
                elif kind == "produtos":
                    vals = [normalize_code(x) for x in vals]
                out.add(tuple(vals))
            if len(rows) < lim: break
            off += lim
    return out

def fill_defaults(row: dict, tbl_dst: Table):
    now = datetime.datetime.now()
    for k in ("created_at","updated_at","criado_em","atualizado_em"):
        if k in row and (row[k] is None or row[k] == ""):
            row[k] = now
    for c in tbl_dst.columns:
        if is_bool_col(c) and c.name in row and row[c.name] is None:
            row[c.name] = False
    return row

def sanitize_row_texts(row: dict, tbl_dst: Table):
    for c in tbl_dst.columns:
        if c.name in row and is_textual_col(c) and isinstance(row[c.name], (str, bytes)):
            row[c.name] = sanitize_text(row[c.name])
    return row

def latest_zip_or_none():
    if not os.path.isdir(BASE_DIR): return None
    zips = [f for f in os.listdir(BASE_DIR) if f.startswith("exports_neon_") and f.endswith(".zip")]
    if not zips: return None
    zips.sort(reverse=True)  # pega o mais recente
    return os.path.join(BASE_DIR, zips[0])

def read_csv_rows_from_zip(zip_path: str, table_name: str, use_cols: list):
    """Generator que lê linhas do CSV <table_name>.csv dentro do zip."""
    if not zip_path: return None
    member_name = f"{table_name}.csv"
    with zipfile.ZipFile(zip_path, "r") as zf:
        if member_name not in zf.namelist():
            return None
        with zf.open(member_name, "r") as f:
            wrapper = TextIOWrapper(f, encoding="utf-8", newline="")
            reader = csv.reader(wrapper)
            header = next(reader, None)
            if not header: return []
            # mapeia índices
            idx = [header.index(c) for c in use_cols if c in header]
            # se faltar coluna importante, devolve vazio para forçar fallback DB
            if len(idx) != len(use_cols): return []
            batch, count = [], 0
            for row in reader:
                obj = {}
                for i, c in enumerate(use_cols):
                    val = row[idx[i]]
                    obj[c] = val if val != "" else None
                batch.append(obj)
                count += 1
                if len(batch) >= BATCH_SIZE:
                    yield batch
                    batch = []
            if batch:
                yield batch

def source_count_db(engine: Engine, tname: str) -> int:
    try:
        with engine.connect() as c:
            return c.execute(text(f'SELECT COUNT(*) FROM "{tname}"')).scalar() or 0
    except SQLAlchemyError:
        return 0

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
    except Exception:
        pass
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
                except IntegrityError:
                    pass
        return ok

def get_fk_sets(engine: Engine, meta: MetaData, tname: str):
    tbl = meta.tables[tname]
    fksets = {}
    with engine.connect() as conn:
        for fk in tbl.foreign_key_constraints:
            for elem in fk.elements:
                ref_tbl = elem.column.table
                ref_col = elem.column
                key = (ref_tbl.name, ref_col.name)
                if key in fksets: continue
                vals = set()
                off, lim = 0, 50000
                while True:
                    rs = conn.execute(select(ref_col).select_from(ref_tbl).limit(lim).offset(off)).fetchall()
                    if not rs: break
                    for r in rs: vals.add(r[0])
                    if len(rs) < lim: break
                    off += lim
                fksets[key] = vals
    return fksets

def create_parent_if_missing(engine: Engine, parent_table: str, parent_id):
    """Cria um registro pai mínimo para produtos, se não existir."""
    if parent_id is None: return
    sql = text(f'INSERT INTO {parent_table} (id, nome) VALUES (:id, :nome) ON CONFLICT (id) DO NOTHING')
    with engine.begin() as conn:
        conn.execute(sql, {"id": parent_id, "nome": f"Importado {parent_id}"})

def maybe_create_product_parents(engine: Engine, row: dict):
    parent_map = {
        "marca_id": ("marca_produto", "id"),
        "tipo_id": ("tipo_produto", "id"),
        "calibre_id": ("calibre_produto", "id"),
        "categoria_id": ("categoria_produto", "id"),
    }
    for fk_col, (ptable, _) in parent_map.items():
        pid = row.get(fk_col)
        if pid:  # cria “pai” mínimo se ainda não existir
            create_parent_if_missing(engine, ptable, pid)

def build_processing_order(meta_dst: MetaData, tables: list):
    # Usa apenas prioridade manual (já suficiente para seu schema)
    prio = {name: i for i, name in enumerate(MANUAL_PRIORITY)}
    tables = [t for t in tables]  # copy
    tables.sort(key=lambda x: prio.get(x, 9999))
    return tables

# ============== Main ==============
def main():
    parser = argparse.ArgumentParser(description="Migrar dados para Locaweb usando ZIP (fallback Neon).")
    parser.add_argument("--only", type=str, default="", help="Lista de tabelas separadas por vírgula (ex.: clientes,produtos)")
    args = parser.parse_args()

    url_neon, url_lw = load_env_or_die()
    eng_src, eng_dst = create_engines()

    meta_src = reflect(eng_src)
    meta_dst = reflect(eng_dst)

    tables = common_tables(meta_src, meta_dst)
    if args.only:
        wanted = set([t.strip() for t in args.only.split(",") if t.strip()])
        tables = [t for t in tables if t in wanted]

    order = build_processing_order(meta_dst, tables)

    # ZIP mais recente (se houver)
    zip_path = latest_zip_or_none()
    log_dir = os.path.join(BASE_DIR, f"migration_logs_{now_tag()}")
    ensure_dir(log_dir)
    summary_rows = []
    summary_header = ["tabela", "linhas_origem", "inseridos", "ignorados", "erros", "chave_usada"]

    print(">> ZIP encontrado:" if zip_path else ">> Nenhum ZIP encontrado; usará Neon quando necessário.", zip_path or "-")

    for tname in order:
        tbl_src = meta_src.tables[tname]
        tbl_dst = meta_dst.tables[tname]
        use_cols = intersect_columns(tbl_src, tbl_dst)
        if not use_cols:
            summary_rows.append([tname, 0, 0, 0, 0, ""])
            continue

        # chaves
        biz_cols, kind = find_business_key_columns(tname, use_cols)
        if biz_cols:
            key_cols = biz_cols
            key_desc = f"business:{'+'.join(key_cols)}"
        else:
            key_cols, kkind = find_pk_or_unique_keys(tbl_dst)
            key_desc = f"{kkind}:{'+'.join(key_cols)}" if key_cols else "all_columns"
            if not key_cols:
                key_cols = use_cols[:]

        existing = preload_existing_keys(eng_dst, tbl_dst, key_cols, kind)

        total_src = total_ins = total_skip = total_err = 0
        errors_log, skipped_log = [], []

        print(f"\n[Tabela {tname}] lendo do ZIP (se existir), senão da Neon | Chave: {key_desc}")

        # Preferir ZIP
        batches = read_csv_rows_from_zip(zip_path, tname, use_cols) if zip_path else None
        if batches is None:
            # Fallback: Neon
            batches = fetch_db_rows(eng_src, tbl_src, use_cols)

        pbar = tqdm(desc=f"{tname}", unit="row")

        for batch in batches:
            total_src += len(batch)
            to_insert = []
            for raw in batch:
                try:
                    # Converter tipagem básica (CSV vem como string)
                    row = dict(raw)
                    # Normalizações de texto e defaults
                    row = sanitize_row_texts(row, tbl_dst)
                    row = fill_defaults(row, tbl_dst)

                    # Ajustes de negócio p/ chaves
                    if kind == "clientes":
                        for cand in CLIENTES_KEY_CANDIDATES:
                            if cand in row and row[cand]:
                                row[cand] = normalize_digits_only(row[cand])
                        if "cpf_cnpj" in row and not row["cpf_cnpj"]:
                            row["cpf_cnpj"] = normalize_digits_only(row.get("documento"))

                    if any(h in tname.lower() for h in PRODUTOS_TABLE_HINTS):
                        for cand in PRODUTOS_KEY_CANDIDATES:
                            if cand in row and row[cand]:
                                row[cand] = normalize_code(row[cand])

                        # Criar pais ausentes automaticamente
                        maybe_create_product_parents(eng_dst, row)

                    ident = build_identifier_key(row, key_cols, kind)
                    if ident in existing:
                        total_skip += 1
                        if len(skipped_log) < 2000:
                            skipped_log.append([json.dumps(row, ensure_ascii=False)])
                        continue

                    to_insert.append(row)

                except Exception as e:
                    total_err += 1
                    if len(errors_log) < 2000:
                        errors_log.append([str(e), json.dumps(raw, ensure_ascii=False)])
                    continue

            # Insert do lote
            try:
                ins = insert_rows(eng_dst, tbl_dst, to_insert, key_cols if key_desc != "all_columns" else None)
                total_ins += ins
                # atualizar cache de chaves
                for r in to_insert[:ins]:
                    existing.add(build_identifier_key(r, key_cols, kind))
            except Exception as e:
                total_err += len(to_insert)
                if len(errors_log) < 2000:
                    errors_log.append([f"batch_error:{str(e)}", f"batch_size={len(to_insert)}"])

            pbar.update(len(batch))

        pbar.close()

        # Logs
        def write_csv(path, rows, header):
            ensure_dir(os.path.dirname(path))
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if header: w.writerow(header)
                w.writerows(rows)

        if skipped_log:
            write_csv(os.path.join(log_dir, f"skipped_{tname}.csv"), skipped_log, ["row_json"])
        if errors_log:
            write_csv(os.path.join(log_dir, f"errors_{tname}.csv"), errors_log, ["error","row_json"])

        summary_rows.append([tname, total_src, total_ins, total_skip, total_err, key_desc])
        print(f"[Resumo {tname}] origem={total_src} | inseridos={total_ins} | ignorados={total_skip} | erros={total_err}")

    # summary
    with open(os.path.join(log_dir, "summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(summary_header); w.writerows(summary_rows)

    print("\n✅ Migração concluída (v3).")
    print("Logs:", log_dir)

if __name__ == "__main__":
    main()
