#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Exporta TODAS as tabelas do banco Neon para CSVs e compacta em um único ZIP.
- Lê DATABASE_URL_NEON do .env
- Salva em C:\precificador-m4\backups_bd\exports_neon_<timestamp>.zip
- CSVs UTF-8, com cabeçalho, leitura em lotes (1000)
- Retomável: se já houver ZIP com mesmo timestamp, cria um novo (novo timestamp)
"""

import os
import sys
import csv
import json
import time
import datetime
import zipfile
from io import StringIO

from dotenv import load_dotenv
from tqdm import tqdm
from sqlalchemy import create_engine, MetaData, Table, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

# === Config ===
BASE_DIR = r"C:\precificador-m4\backups_bd"
BATCH_SIZE = 1000

def now_tag():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def load_env_or_die():
    load_dotenv()
    url = os.getenv("DATABASE_URL_NEON")
    if not url:
        print("ERRO: defina DATABASE_URL_NEON no .env", file=sys.stderr)
        sys.exit(1)
    return url

def create_engine_neon():
    url = load_env_or_die()
    return create_engine(url)

def reflect_all(engine: Engine):
    meta = MetaData()
    meta.reflect(bind=engine)
    return meta

def table_rowcount(engine: Engine, table_name: str) -> int:
    try:
        with engine.connect() as conn:
            return conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar() or 0
    except SQLAlchemyError:
        return 0

def export_table_to_csv_string(engine: Engine, table: Table) -> str:
    """Exporta a tabela para um CSV em memória (string) em lotes."""
    output = StringIO()
    writer = None

    total = table_rowcount(engine, table.name)
    pbar = tqdm(total=total, desc=f"Export {table.name}", unit="row")

    with engine.connect() as conn:
        offset = 0
        cols = [c.name for c in table.columns]
        while True:
            stmt = select(*[table.c[c] for c in cols]).limit(BATCH_SIZE).offset(offset)
            rows = conn.execute(stmt).fetchall()
            if not rows:
                break

            if writer is None:
                writer = csv.writer(output, lineterminator="\n")
                writer.writerow(cols)

            for r in rows:
                # converte para tipos serializáveis simples
                safe = []
                for v in r:
                    if v is None:
                        safe.append("")
                    elif isinstance(v, (datetime.date, datetime.datetime)):
                        safe.append(v.isoformat())
                    else:
                        safe.append(v)
                writer.writerow(safe)

            offset += len(rows)
            pbar.update(len(rows))
    pbar.close()
    return output.getvalue()

def main():
    print(">> Exportador Neon -> CSV (ZIP único)")
    ensure_dir(BASE_DIR)

    eng = create_engine_neon()
    meta = reflect_all(eng)

    ts = now_tag()
    zip_path = os.path.join(BASE_DIR, f"exports_neon_{ts}.zip")
    print(f">> Gerando arquivo: {zip_path}")

    # Cria ZIP e escreve cada tabela como "<tabela>.csv"
    with zipfile.ZipFile(zip_path, mode="x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for tname in sorted(meta.tables.keys()):
            table = meta.tables[tname]
            try:
                csv_text = export_table_to_csv_string(eng, table)
                zf.writestr(f"{tname}.csv", csv_text.encode("utf-8"))
            except Exception as e:
                # Se uma tabela falhar, seguimos para as próximas (log básico)
                error_info = f"# ERROR exporting {tname}: {e}\n"
                zf.writestr(f"{tname}__EXPORT_ERROR.txt", error_info.encode("utf-8"))
                print(error_info.strip())

    print("✅ Exportação concluída.")
    print("Arquivo ZIP:", zip_path)

if __name__ == "__main__":
    main()
