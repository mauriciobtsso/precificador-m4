#!/usr/bin/env python3
"""Compare o OCR local atual do M4 com pdf_oxide em uma pasta de PDFs.

O script não chama Groq/OCR.Space, não grava no banco e não altera os PDFs.
Por padrão, o relatório contém apenas métricas e identificadores SHA-256 curtos.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any

DEFAULT_MAX_PAGES = 3  # mesmo limite configurado no pipeline atual do M4


def _sha_id(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _page_stats(texts: list[str]) -> dict[str, Any]:
    clean = [text or "" for text in texts]
    return {
        "pages_processed": len(clean),
        "pages_with_text": sum(bool(text.strip()) for text in clean),
        "pages_with_at_least_30_chars": sum(len(text.strip()) >= 30 for text in clean),
        "characters": sum(len(text) for text in clean),
        "non_whitespace_characters": sum(len("".join(text.split())) for text in clean),
    }


def _load_current_extractor():
    """Carrega só app/services/ocr_local.py, sem importar app/__init__.py."""
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "app" / "services" / "ocr_local.py"
    spec = importlib.util.spec_from_file_location("m4_ocr_local_for_comparison", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("não foi possível localizar app/services/ocr_local.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.extract_text_local


def _run_current_local(pdf_bytes: bytes, filename: str, max_pages: int) -> dict[str, Any]:
    extract_text_local = _load_current_extractor()
    result = extract_text_local(
        file_bytes=pdf_bytes,
        filename=filename,
        lang="por+eng",
        dpi=200,
        max_pages=max_pages,
        try_pdf_textlayer=True,
        compute_confidence=False,
    )
    texts = [str(text or "") for text in result.get("texts", [])]
    return {
        "engine": "m4_local_pdfplumber_tesseract",
        "success": True,
        "stats": _page_stats(texts),
        "truncated": bool((result.get("meta") or {}).get("truncated")),
        "used_pdf_textlayer": bool(result.get("used_pdf_textlayer")),
        "textlayer_score": (result.get("meta") or {}).get("pdf_textlayer_score"),
        "avg_confidence": result.get("avg_confidence"),
        "texts": texts,
    }


def _run_pdf_oxide(pdf_bytes: bytes, max_pages: int, language: str) -> dict[str, Any]:
    try:
        from pdf_oxide import PdfDocument
    except ImportError as exc:
        raise RuntimeError(
            "pdf_oxide ausente; instale-o seguindo tools/ocr_comparison/README.md"
        ) from exc

    # A API aceita opções parciais; `pt` é alias oficial para o modelo Latin.
    options = json.dumps({"ocr_languages": [language]})
    texts: list[str] = []
    page_details: list[dict[str, Any]] = []
    with PdfDocument.from_bytes(pdf_bytes) as doc:
        total_pages = int(doc.page_count())
        page_limit = min(total_pages, max_pages)
        for page_index in range(page_limit):
            try:
                extracted = json.loads(doc.extract_page_auto(page_index, options))
                text = str(extracted.get("text") or "")
                texts.append(text)
                page_details.append({
                    "page": page_index + 1,
                    "kind": extracted.get("kind"),
                    "status": extracted.get("status"),
                    "confidence": extracted.get("confidence"),
                    "ocr_used": extracted.get("ocr_used"),
                    "error": None,
                })
            except Exception as exc:  # preserva resultados das demais páginas
                texts.append("")
                page_details.append({"page": page_index + 1, "error": type(exc).__name__})

    return {
        "engine": "pdf_oxide_auto",
        "success": True,
        "source_pages": total_pages,
        "truncated": total_pages > page_limit,
        "language_hint": language,
        "stats": _page_stats(texts),
        "pages": page_details,
        "texts": texts,
    }


def _safe_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _save_texts(folder: Path, doc_id: str, engines: dict[str, dict[str, Any]]) -> list[str]:
    written: list[str] = []
    for engine_key, result in engines.items():
        if not result.get("success"):
            continue
        for page_number, text in enumerate(result.get("texts", []), start=1):
            target = folder / engine_key / f"{doc_id}_p{page_number:03d}.txt"
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                target.parent.chmod(0o700)
            except OSError:
                pass
            target.write_text(text, encoding="utf-8")
            try:
                target.chmod(0o600)
            except OSError:
                pass
            written.append(str(target))
    return written


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path, help="Pasta de PDFs da amostra (recursiva).")
    parser.add_argument("--output", type=Path, default=Path("ocr_comparison.json"), help="Relatório JSON de métricas; não contém texto por padrão.")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES, help="Máximo por PDF (padrão: 3, como no M4).")
    parser.add_argument("--language", default="pt", help="Dica pdf_oxide; `pt` seleciona o modelo Latin (padrão: pt).")
    parser.add_argument("--save-text", action="store_true", help="Opt-in: grava OCR bruto localmente; contém dados pessoais.")
    parser.add_argument("--include-filenames", action="store_true", help="Opt-in: inclui nomes relativos no relatório; podem conter dados pessoais.")
    parser.add_argument("--prefetch-oxide-models", action="store_true", help="Baixa modelos pdf_oxide uma vez, usando a rede, antes do teste.")
    args = parser.parse_args()
    if args.max_pages < 1:
        parser.error("--max-pages deve ser maior que zero")
    if not args.input_dir.is_dir():
        parser.error(f"--input-dir não existe ou não é pasta: {args.input_dir}")
    return args


def main() -> int:
    args = _parse_args()
    root = args.input_dir.resolve()
    files = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() == ".pdf")
    if not files:
        print("Nenhum PDF encontrado.", file=sys.stderr)
        return 2

    if args.prefetch_oxide_models:
        try:
            try:
                from pdf_oxide import prefetch_models
            except ImportError:
                # O wheel 0.3.78 publica esta função no módulo nativo,
                # embora a referência Rust upstream também cite o topo.
                from pdf_oxide.pdf_oxide import prefetch_models
            model_dir = prefetch_models([args.language])
            print(f"Modelos pdf_oxide provisionados em: {model_dir}")
        except Exception as exc:
            print(f"Falha ao provisionar modelos pdf_oxide ({type(exc).__name__}).", file=sys.stderr)
            return 2

    records: list[dict[str, Any]] = []
    text_folder = args.output.parent / (args.output.stem + "_texts")
    for index, path in enumerate(files, start=1):
        data = path.read_bytes()
        doc_id = _sha_id(data)
        identity: dict[str, Any] = {"document_id": doc_id, "extension": ".pdf"}
        if args.include_filenames:
            identity["relative_filename"] = path.relative_to(root).as_posix()

        engines: dict[str, dict[str, Any]] = {}
        for key, runner in (
            ("m4_local", lambda: _run_current_local(data, path.name, args.max_pages)),
            ("pdf_oxide", lambda: _run_pdf_oxide(data, args.max_pages, args.language)),
        ):
            started = time.perf_counter()
            try:
                result = runner()
                result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            except Exception as exc:
                result = {
                    "engine": key,
                    "success": False,
                    "error": type(exc).__name__,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                }
            engines[key] = result

        record: dict[str, Any] = {**identity, "engines": engines}
        if args.save_text:
            record["text_files"] = _save_texts(text_folder, doc_id, engines)
        for result in engines.values():
            result.pop("texts", None)  # nunca incluir texto bruto no JSON
        records.append(record)
        statuses = ", ".join(f"{key}={'ok' if value['success'] else 'falha'}" for key, value in engines.items())
        print(f"[{index}/{len(files)}] id={doc_id} {statuses}")

    summary = {
        "schema_version": 1,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "comparison_scope": "OCR/text extraction only; no LLM, OCR.Space, database, or persistence",
        "max_pages_per_pdf": args.max_pages,
        "pdf_oxide_language_hint": args.language,
        "documents_total": len(records),
        "m4_local_successes": sum(row["engines"]["m4_local"]["success"] for row in records),
        "pdf_oxide_successes": sum(row["engines"]["pdf_oxide"]["success"] for row in records),
        "documents": records,
        "text_files_directory": str(text_folder) if args.save_text else None,
    }
    _safe_write_json(args.output, summary)
    print(f"Relatório salvo com permissões restritas: {args.output}")
    if args.save_text:
        print(f"ATENÇÃO: OCR bruto pode conter dados pessoais; arquivos em {text_folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
