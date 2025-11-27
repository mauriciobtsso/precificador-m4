# ============================================================
# MÓDULO: COMPRAS — Parser híbrido de NF-e (XML + LLM fallback)
# v7A.5 (Suporte a múltiplos serials por item)
# ============================================================

from datetime import datetime
from decimal import Decimal
import os
import re

# Preferir lxml, com fallback seguro para ElementTree
try:
    from lxml import etree as LET
    _LXML_OK = True
except Exception:
    _LXML_OK = False

import xml.etree.ElementTree as ET

# Import só quando disponível (evita dependência dura fora do Flask)
try:
    from flask import current_app
except Exception:  # noqa
    current_app = None

from app.compras.utils_llm import analisar_nf_xml_conteudo


# ============================================================
# Helpers de logging
# ============================================================
def _is_debug():
    """Detecta se deve logar em modo debug."""
    try:
        if current_app and getattr(current_app, "debug", False):
            return True
    except Exception:
        pass
    # Fallback por env
    return os.environ.get("FLASK_DEBUG") in {"1", "true", "True"} or os.environ.get("M4_DEBUG") in {"1", "true", "True"}


def _dlog(msg):
    """Log enxuto para depuração."""
    if _is_debug():
        print(f"[NF-DEBUG] {msg}")


# ============================================================
# Utilitários
# ============================================================
_DIGITS_RE = re.compile(r"\D+")

def _only_digits(s: str) -> str:
    return _DIGITS_RE.sub("", s or "")

def _strip_ns_etree(elem):
    """Remove namespace in-place (ElementTree)."""
    for e in elem.iter():
        if "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]

def _qtext(node, path, ns=None):
    """XPath text helper (lxml). Usa local-name() nos paths do chamador."""
    if node is None:
        return ""
    try:
        found = node.xpath(path, namespaces=ns or {})
        if not found:
            return ""
        if hasattr(found[0], "text"):
            return (found[0].text or "").strip()
        return (str(found[0]) or "").strip()
    except Exception:
        return ""

def _to_decimal(txt):
    if txt is None:
        return Decimal(0)
    s = str(txt).strip()
    if not s:
        return Decimal(0)
    try:
        return Decimal(s.replace(",", "."))
    except Exception:
        return Decimal(0)

def _parse_datetime_emi(dhEmi, dEmi):
    """
    dhEmi (ex.: 2025-10-22T13:01:00-03:00) | dEmi (YYYY-MM-DD)
    Retorna string ISO padrão (fromisoformat aceita ±HH:MM).
    """
    val = (dhEmi or dEmi or "").strip()
    if not val:
        return ""
    if val.endswith("Z"):
        val = val.replace("Z", "+00:00")
    return val

def _sum_itens_total(itens):
    total = Decimal(0)
    for it in itens or []:
        try:
            q = Decimal(str(it.get("quantidade") or 0))
            v = Decimal(str(it.get("valor_unitario") or 0))
            total += q * v
        except Exception:
            pass
    return total

def _normalize_chave(ch):
    """Garante 44 dígitos. Remove prefixo 'NFe' e lixo não numérico."""
    if not ch:
        return ""
    ch = ch.strip()
    if ch.startswith("NFe"):
        ch = ch[3:]
    ch = _only_digits(ch)
    # Em casos raros, a chave pode estar com prefixos/sufixos — ficar só com os últimos 44 dígitos.
    if len(ch) > 44:
        ch = ch[-44:]
    return ch


# ============================================================
# Parser principal — detecta e lê todos os padrões de NF-e
# ============================================================
def parse_nf_xml_inteligente(file):
    """
    Lê o XML da NF-e (arma, munição, etc), extrai:
    - Fornecedor (emit/xNome)
    - CNPJ (emit/CNPJ)
    - Número (ide/nNF)
    - Chave (infNFe@Id sem 'NFe' ou protNFe/infProt/chNFe) → normalizada p/ 44 dígitos
    - Data de emissão (ide/dhEmi ou ide/dEmi)
    - Valor total (total/ICMSTot/vNF, com fallbacks)
    - Itens (det/prod) + dados de arma (det/prod/arma)
    Se falhar, usa fallback via LLM.
    """
    try:
        xml_bytes = file.read()
        xml_content = xml_bytes.decode("utf-8", errors="ignore")

        fornecedor = ""
        cnpj_emit = ""
        numero = ""
        data_emissao = ""
        chave = ""
        valor_total_nf = Decimal(0)
        itens = []

        # =======================
        # TENTAR COM LXML
        # =======================
        if _LXML_OK:
            try:
                parser = LET.XMLParser(recover=True, huge_tree=True, remove_blank_text=True)
                raiz = LET.fromstring(xml_content.encode("utf-8"), parser=parser)

                # ---------- localizar <infNFe> de forma robusta ----------
                info_nf = None
                busca_caminhos = [
                    ".//*[local-name()='infNFe']",
                    ".//NFe/*[local-name()='infNFe']",
                    ".//nfeProc/*[local-name()='NFe']/*[local-name()='infNFe']",
                    "./*[local-name()='NFe']/*[local-name()='infNFe']",
                    "./*[local-name()='nfeProc']/*[local-name()='NFe']/*[local-name()='infNFe']",
                ]
                for path in busca_caminhos:
                    encontrados = raiz.xpath(path)
                    if encontrados:
                        info_nf = encontrados[0]
                        break

                if info_nf is None:
                    _dlog("infNFe não encontrado com lxml — tentando ET fallback.")
                    raise ValueError("infNFe não encontrado")

                # ---------- CHAVE ----------
                chave_attr = (info_nf.get("Id") or "").strip()
                chave = _normalize_chave(chave_attr)
                if not chave:
                    # protNFe/infProt/chNFe (nfeProc)
                    ch_paths = [
                        ".//*[local-name()='protNFe']/*[local-name()='infProt']/*[local-name()='chNFe']",
                        ".//nfeProc/*[local-name()='protNFe']/*[local-name()='infProt']/*[local-name()='chNFe']",
                        ".//*[local-name()='chNFe']",
                    ]
                    for cp in ch_paths:
                        v = _qtext(raiz, cp)
                        v = _normalize_chave(v)
                        if v:
                            chave = v
                            break
                _dlog(f"Chave extraída (lxml): {chave}")

                # ---------- IDE / EMIT ----------
                ide = None
                for p in [".//*[local-name()='ide']", "./*[local-name()='ide']"]:
                    r = info_nf.xpath(p)
                    if r:
                        ide = r[0]
                        break

                emit = None
                for p in [".//*[local-name()='emit']", "./*[local-name()='emit']"]:
                    r = info_nf.xpath(p)
                    if r:
                        emit = r[0]
                        break

                numero = _qtext(ide, ".//*[local-name()='nNF']")
                dhEmi = _qtext(ide, ".//*[local-name()='dhEmi']")
                dEmi = _qtext(ide, ".//*[local-name()='dEmi']")
                data_emissao = _parse_datetime_emi(dhEmi, dEmi)

                fornecedor = _qtext(emit, ".//*[local-name()='xNome']") or _qtext(emit, ".//*[local-name()='xFant']")
                cnpj_emit = _only_digits(_qtext(emit, ".//*[local-name()='CNPJ']"))

                # Evita duplicação quando xNome e xFant são semelhantes (caso CBC)
                if fornecedor:
                    parts = fornecedor.split()
                    fornecedor = " ".join(sorted(set(parts), key=parts.index))

                _dlog(f"Fornec/CNPJ (lxml): {fornecedor} / {cnpj_emit}")


                # ---------- Valor Total ----------
                # padrão
                vNF = _qtext(info_nf, ".//*[local-name()='total']/*[local-name()='ICMSTot']/*[local-name()='vNF']")
                valor_total_nf = _to_decimal(vNF)
                # leniência: qualquer vNF dentro de infNFe
                if valor_total_nf == Decimal(0):
                    vNF_any = _qtext(info_nf, ".//*[local-name()='vNF']")
                    valor_total_nf = _to_decimal(vNF_any)
                _dlog(f"Valor total inicial (lxml): {valor_total_nf}")

                # ---------- ITENS ----------
                dets = info_nf.xpath(".//*[local-name()='det']")
                for det in dets:
                    # prod como filho ou descendente
                    prod_candidates = det.xpath("./*[local-name()='prod']") or det.xpath(".//*[local-name()='prod']")
                    prod = prod_candidates[0] if prod_candidates else None
                    if prod is None:
                        continue

                    descricao = _qtext(prod, ".//*[local-name()='xProd']")
                    ncm = _qtext(prod, ".//*[local-name()='NCM']")
                    calibre = _qtext(prod, ".//*[local-name()='calibre']")
                    modelo = _qtext(prod, ".//*[local-name()='modelo']")
                    marca = _qtext(prod, ".//*[local-name()='marca']")
                    lote = _qtext(prod, ".//*[local-name()='lote']")

                    qCom = _to_decimal(_qtext(prod, ".//*[local-name()='qCom']"))
                    vUnCom = _to_decimal(_qtext(prod, ".//*[local-name()='vUnCom']"))

                    # --- MÚLTIPLAS ARMAS (NOVO) ---
                    armas_nodes = prod.xpath("./*[local-name()='arma']") or prod.xpath(".//*[local-name()='arma']")
                    lista_seriais = []
                    
                    # Pega a primeira arma como referência para campos legados
                    tpArma_ref = ""
                    nCano_ref = ""
                    descr_arma_ref = ""

                    if armas_nodes:
                        tpArma_ref = _qtext(armas_nodes[0], ".//*[local-name()='tpArma']")
                        nCano_ref = _qtext(armas_nodes[0], ".//*[local-name()='nCano']")
                        descr_arma_ref = _qtext(armas_nodes[0], ".//*[local-name()='descr']")

                    for arma in armas_nodes:
                        nSerie = _qtext(arma, ".//*[local-name()='nSerie']")
                        if nSerie:
                            lista_seriais.append(nSerie)
                    
                    # Junta todos os serials separados por vírgula
                    seriais_str = ",".join(lista_seriais) if lista_seriais else ""

                    item = {
                        "descricao": (descricao or descr_arma_ref or "").strip(),
                        "marca": marca,
                        "modelo": modelo,
                        "calibre": calibre,
                        "lote": lote,
                        "ncm": ncm,
                        "quantidade": float(qCom),
                        "valor_unitario": float(vUnCom),
                        "valor_total": float(qCom * vUnCom),
                        "tpArma": tpArma_ref,
                        
                        # NOVOS CAMPOS
                        "seriais_xml": seriais_str, 
                        "numero_serie": lista_seriais[0] if lista_seriais else "", # Compatibilidade
                        
                        "nCano": nCano_ref,
                        "descricao_arma": descr_arma_ref,
                    }
                    itens.append(item)

                _dlog(f"Itens encontrados (lxml): {len(itens)}")

            except Exception as e:
                _dlog(f"Falha lxml: {e}")
                info_nf = None
        else:
            info_nf = None

        # =======================
        # FALLBACK COM ElementTree
        # =======================
        if not _LXML_OK or info_nf is None:
            raiz = ET.fromstring(xml_content)
            _strip_ns_etree(raiz)

            info_nf = (raiz.find(".//infNFe")
                       or raiz.find(".//NFe/infNFe")
                       or raiz.find(".//nfeProc/NFe/infNFe"))
            if info_nf is None:
                return {"success": False, "error": "Não foi possível localizar o bloco infNFe no XML."}

            # Chave
            chave_attr = (info_nf.attrib.get("Id") or "").strip()
            chave = _normalize_chave(chave_attr)
            if not chave:
                ch_node = (raiz.find(".//protNFe/infProt/chNFe")
                           or raiz.find(".//nfeProc/protNFe/infProt/chNFe")
                           or raiz.find(".//chNFe"))
                if ch_node is not None and (ch_node.text or "").strip():
                    chave = _normalize_chave(ch_node.text)
            _dlog(f"Chave extraída (ET): {chave}")

            # ide/emit como descendentes
            ide = (info_nf.find(".//ide") or info_nf.find("ide"))
            emit = (info_nf.find(".//emit") or info_nf.find("emit"))

            numero = (ide.findtext("nNF") if ide is not None else "") or (ide.findtext(".//nNF") if ide is not None else "") or ""
            dhEmi = (ide.findtext("dhEmi") if ide is not None else "") or (ide.findtext(".//dhEmi") if ide is not None else "") or ""
            dEmi = (ide.findtext("dEmi") if ide is not None else "") or (ide.findtext(".//dEmi") if ide is not None else "") or ""
            data_emissao = _parse_datetime_emi(dhEmi, dEmi)

            fornecedor = ((emit.findtext("xNome") or emit.findtext(".//xNome")) if emit is not None else "") or ""
            cnpj_emit = _only_digits(((emit.findtext("CNPJ") or emit.findtext(".//CNPJ")) if emit is not None else "") or "")
            _dlog(f"Fornec/CNPJ (ET): {fornecedor} / {cnpj_emit}")

            # Valor total
            total_icms = info_nf.find(".//total/ICMSTot") or info_nf.find("total/ICMSTot")
            vNF_text = total_icms.findtext("vNF") if total_icms is not None else ""
            valor_total_nf = _to_decimal(vNF_text or (info_nf.findtext(".//vNF") or ""))
            _dlog(f"Valor total inicial (ET): {valor_total_nf}")

            # Itens
            for det in info_nf.findall(".//det"):
                prod = det.find(".//prod") or det.find("prod")
                if prod is None:
                    continue

                descricao = (prod.findtext(".//xProd") or prod.findtext("xProd") or "").strip()
                ncm = (prod.findtext(".//NCM") or prod.findtext("NCM") or "").strip()
                calibre = (prod.findtext(".//calibre") or prod.findtext("calibre") or "").strip()
                modelo = (prod.findtext(".//modelo") or prod.findtext("modelo") or "").strip()
                marca = (prod.findtext(".//marca") or prod.findtext("marca") or "").strip()
                lote = (prod.findtext(".//lote") or prod.findtext("lote") or "").strip()

                quantidade = _to_decimal(prod.findtext(".//qCom") or prod.findtext("qCom") or "0")
                valor_unitario = _to_decimal(prod.findtext(".//vUnCom") or prod.findtext("vUnCom") or "0")

                # --- MÚLTIPLAS ARMAS (FALLBACK) ---
                armas_nodes = prod.findall(".//arma") or prod.findall("arma")
                lista_seriais = []
                tpArma_ref = ""
                nCano_ref = ""
                descr_arma_ref = ""

                if armas_nodes:
                    tpArma_ref = armas_nodes[0].findtext("tpArma") or ""
                    nCano_ref = armas_nodes[0].findtext("nCano") or ""
                    descr_arma_ref = armas_nodes[0].findtext("descr") or ""

                for arma in armas_nodes:
                    nSerie = arma.findtext("nSerie")
                    if nSerie:
                        lista_seriais.append(nSerie.strip())

                seriais_str = ",".join(lista_seriais) if lista_seriais else ""

                item = {
                    "descricao": descricao or (descr_arma_ref or ""),
                    "marca": marca,
                    "modelo": modelo,
                    "calibre": calibre,
                    "lote": lote,
                    "ncm": ncm,
                    "quantidade": float(quantidade),
                    "valor_unitario": float(valor_unitario),
                    "valor_total": float(quantidade * valor_unitario),
                    "tpArma": tpArma_ref,
                    "seriais_xml": serials_str, # Novo campo
                    "numero_serie": lista_seriais[0] if lista_seriais else "",
                    "nCano": nCano_ref,
                    "descricao_arma": descr_arma_ref,
                }
                itens.append(item)

        # =======================
        # FALLBACK VIA LLM (se não houver itens)
        # =======================
        if not itens:
            _dlog("Nenhum item via XML — acionando LLM.")
            try:
                itens = analisar_nf_xml_conteudo(xml_content) or []
            except Exception as e:
                return {"success": False, "error": f"Falha no LLM: {e}"}

        # Último fallback para valor_total: soma dos itens
        if valor_total_nf == Decimal(0) and itens:
            valor_total_nf = _sum_itens_total(itens)
            _dlog(f"Valor total por soma de itens: {valor_total_nf}")

        # =======================
        # RETORNO FINAL
        # =======================
        return {
            "success": True,
            "fornecedor": fornecedor or "",
            "cnpj_emit": cnpj_emit or "",
            "chave": chave or "",
            "numero": numero or "",
            "data_emissao": data_emissao or "",
            "valor_total": float(valor_total_nf),     # novo nome padronizado
            "valor_total_nf": float(valor_total_nf),  # compat legado
            "itens": itens,
        }

    except ET.ParseError:
        return {"success": False, "error": "Erro ao ler o XML."}
    except Exception as e:
        return {"success": False, "error": f"Erro no parser híbrido: {e}"}