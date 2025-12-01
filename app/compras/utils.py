# ============================================================
# MÓDULO: COMPRAS — Parser híbrido de NF-e (XML + LLM fallback)
# v9.0 (Versão INTEGRAL: Suporte a Rastro, Lote, Vol e Armas)
# ============================================================

from datetime import datetime
from decimal import Decimal
import os
import re

# Tenta importar lxml para performance e suporte a namespaces
try:
    from lxml import etree as LET
    _LXML_OK = True
except Exception:
    _LXML_OK = False

import xml.etree.ElementTree as ET

# Importa current_app apenas se estiver rodando no Flask
try:
    from flask import current_app
except Exception:  # noqa
    current_app = None

from app.compras.utils_llm import analisar_nf_xml_conteudo


# ============================================================
# Helpers de logging e Configuração
# ============================================================
def _is_debug():
    """Detecta se deve logar em modo debug."""
    try:
        if current_app and getattr(current_app, "debug", False):
            return True
    except Exception:
        pass
    return os.environ.get("FLASK_DEBUG") in {"1", "true", "True"} or os.environ.get("M4_DEBUG") in {"1", "true", "True"}


def _dlog(msg):
    """Log enxuto para depuração."""
    if _is_debug():
        print(f"[NF-PARSER] {msg}")


# ============================================================
# Utilitários de Texto e Conversão
# ============================================================
_DIGITS_RE = re.compile(r"\D+")

def _only_digits(s: str) -> str:
    """Remove tudo que não for dígito."""
    return _DIGITS_RE.sub("", s or "")

def _strip_ns_etree(elem):
    """Remove namespace in-place (ElementTree)."""
    for e in elem.iter():
        if "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]

def _qtext(node, path, ns=None):
    """
    XPath text helper (lxml). 
    Usa local-name() nos paths para ignorar namespaces complexos da SEFAZ.
    """
    if node is None:
        return ""
    try:
        # XPath agnóstico de namespace: .//*[local-name()='tag']
        found = node.xpath(path, namespaces=ns or {})
        if not found:
            return ""
        if hasattr(found[0], "text"):
            return (found[0].text or "").strip()
        return (str(found[0]) or "").strip()
    except Exception:
        return ""

def _to_decimal(txt):
    """Converte string (com vírgula ou ponto) para Decimal seguro."""
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
    Tenta extrair data de emissão.
    Prioriza dhEmi (DataHora com timezone) sobre dEmi (Data simples).
    """
    val = (dhEmi or dEmi or "").strip()
    if not val:
        return ""
    if val.endswith("Z"):
        val = val.replace("Z", "+00:00")
    return val

def _sum_itens_total(itens):
    """Recalcula total da nota somando os itens."""
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
    """
    Garante chave de 44 dígitos. 
    Remove prefixo 'NFe' e caracteres estranhos.
    """
    if not ch:
        return ""
    ch = ch.strip()
    if ch.startswith("NFe"):
        ch = ch[3:]
    ch = _only_digits(ch)
    # Em casos raros, a chave pode vir com sufixos
    if len(ch) > 44:
        ch = ch[-44:]
    return ch


# ============================================================
# Parser Principal — Lógica Híbrida (LXML > ET > LLM)
# ============================================================
def parse_nf_xml_inteligente(file):
    """
    Lê o XML da NF-e e extrai dados estruturados.
    Campos extraídos:
    - Cabeçalho: Fornecedor, CNPJ, Número, Série, Chave, Data, Total.
    - Itens: Código, Descrição, NCM, CFOP, Unidade, Qtd, Valor.
    - Específicos: 
        - Armas (nSerie, nCano, tpArma)
        - Rastreabilidade (nLote, qLote, dFab, dVal) -> Para munições/remédios
        - Veículos (chassi) - se houver
        - Combustível - se houver
    - Transporte: Volumes (nVol, esp)
    """
    try:
        # Lê o arquivo para memória
        xml_bytes = file.read()
        # Tenta decodificar (utf-8 ou latin-1)
        try:
            xml_content = xml_bytes.decode("utf-8")
        except UnicodeDecodeError:
            xml_content = xml_bytes.decode("latin-1", errors="ignore")

        # Estrutura de retorno padrão
        dados = {
            "success": True, 
            "fornecedor": "", 
            "cnpj_emit": "", 
            "chave": "", 
            "numero": "", 
            "serie": "",
            "data_emissao": "", 
            "valor_total": 0.0, 
            "itens": []
        }

        # ==================================================
        # 1. TENTATIVA COM LXML (Prioritária - Mais rápida)
        # ==================================================
        if _LXML_OK:
            try:
                parser = LET.XMLParser(recover=True, huge_tree=True, remove_blank_text=True)
                raiz = LET.fromstring(xml_content.encode("utf-8"), parser=parser)

                # Localiza o bloco <infNFe>
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
                    raise ValueError("infNFe não encontrado via LXML")

                # --- CHAVE DE ACESSO ---
                chave_attr = (info_nf.get("Id") or "").strip()
                dados["chave"] = _normalize_chave(chave_attr)
                
                if not dados["chave"]:
                    # Tenta buscar na tag protNFe (comum em XMLs de distribuição)
                    ch_paths = [
                        ".//*[local-name()='protNFe']/*[local-name()='infProt']/*[local-name()='chNFe']",
                        ".//nfeProc/*[local-name()='protNFe']/*[local-name()='infProt']/*[local-name()='chNFe']",
                        ".//*[local-name()='chNFe']",
                    ]
                    for cp in ch_paths:
                        v = _qtext(raiz, cp)
                        v = _normalize_chave(v)
                        if v:
                            dados["chave"] = v
                            break

                # --- DADOS DA NOTA (IDE) ---
                ide = info_nf.xpath(".//*[local-name()='ide']")[0]
                dados["numero"] = _qtext(ide, ".//*[local-name()='nNF']")
                dados["serie"] = _qtext(ide, ".//*[local-name()='serie']")
                
                dh = _qtext(ide, ".//*[local-name()='dhEmi']")
                de = _qtext(ide, ".//*[local-name()='dEmi']")
                dados["data_emissao"] = _parse_datetime_emi(dh, de)

                # --- EMITENTE (EMIT) ---
                emit = info_nf.xpath(".//*[local-name()='emit']")[0]
                dados["fornecedor"] = _qtext(emit, ".//*[local-name()='xNome']") or _qtext(emit, ".//*[local-name()='xFant']")
                dados["cnpj_emit"] = _only_digits(_qtext(emit, ".//*[local-name()='CNPJ']"))
                
                # Limpeza de nome duplicado
                if dados["fornecedor"]:
                    parts = dados["fornecedor"].split()
                    # Remove duplicatas consecutivas mantendo a ordem
                    dados["fornecedor"] = " ".join(sorted(set(parts), key=parts.index))

                # --- VALOR TOTAL ---
                vNF = _qtext(info_nf, ".//*[local-name()='total']/*[local-name()='ICMSTot']/*[local-name()='vNF']")
                valor_dec = _to_decimal(vNF)
                # Se zerado, tenta pegar de qualquer tag vNF (alguns xmls simplificados)
                if valor_dec == Decimal(0):
                    vNF_any = _qtext(info_nf, ".//*[local-name()='vNF']")
                    valor_dec = _to_decimal(vNF_any)
                
                dados["valor_total"] = float(valor_dec)

                # --- DADOS DE TRANSPORTE (EMBALAGEM) ---
                embalagem_global = ""
                transp = info_nf.xpath(".//*[local-name()='transp']")
                if transp:
                    vol = transp[0].xpath(".//*[local-name()='vol']")
                    if vol:
                        # Tenta pegar 'esp' (espécie: CAIXA, VOL) e 'nVol' (numeração)
                        esp = _qtext(vol[0], ".//*[local-name()='esp']")
                        nVol = _qtext(vol[0], ".//*[local-name()='nVol']")
                        if nVol:
                            embalagem_global = f"{esp} {nVol}".strip()
                        elif esp:
                            embalagem_global = esp

                # --- ITENS (DET) ---
                dets = info_nf.xpath(".//*[local-name()='det']")
                for det in dets:
                    prod = det.xpath(".//*[local-name()='prod']")[0]
                    
                    # Dados Básicos
                    codigo = _qtext(prod, ".//*[local-name()='cProd']")
                    descricao = _qtext(prod, ".//*[local-name()='xProd']")
                    ncm = _qtext(prod, ".//*[local-name()='NCM']")
                    cfop = _qtext(prod, ".//*[local-name()='CFOP']")
                    uCom = _qtext(prod, ".//*[local-name()='uCom']")
                    
                    qCom = _to_decimal(_qtext(prod, ".//*[local-name()='qCom']"))
                    vUnCom = _to_decimal(_qtext(prod, ".//*[local-name()='vUnCom']"))
                    vProd = _to_decimal(_qtext(prod, ".//*[local-name()='vProd']"))

                    # --- EXTRAÇÃO DE ARMAS ---
                    armas_nodes = prod.xpath("./*[local-name()='arma']") or prod.xpath(".//*[local-name()='arma']")
                    lista_seriais = []
                    
                    tpArma_ref = ""
                    nCano_ref = ""
                    descr_arma_ref = ""

                    if armas_nodes:
                        # Pega detalhes da primeira arma para referência
                        tpArma_ref = _qtext(armas_nodes[0], ".//*[local-name()='tpArma']")
                        nCano_ref = _qtext(armas_nodes[0], ".//*[local-name()='nCano']")
                        descr_arma_ref = _qtext(armas_nodes[0], ".//*[local-name()='descr']")

                    for arma in armas_nodes:
                        nSerie = _qtext(arma, ".//*[local-name()='nSerie']")
                        if nSerie:
                            lista_seriais.append(nSerie)
                    
                    seriais_str = ",".join(lista_seriais) if lista_seriais else ""

                    # --- EXTRAÇÃO DE RASTREABILIDADE (MUNIÇÃO/REMÉDIO) ---
                    lote_xml = _qtext(prod, ".//*[local-name()='lote']") # Tag antiga/simples
                    dVal_xml = ""
                    dFab_xml = ""

                    # Tag <rastro> (Padrão novo para munições)
                    if not lote_xml:
                        rastros = prod.xpath(".//*[local-name()='rastro']")
                        if rastros:
                            # Pega do primeiro lote encontrado (geralmente 1 por item)
                            lote_xml = _qtext(rastros[0], ".//*[local-name()='nLote']")
                            dFab_xml = _qtext(rastros[0], ".//*[local-name()='dFab']")
                            dVal_xml = _qtext(rastros[0], ".//*[local-name()='dVal']")

                    item = {
                        "codigo_xml": codigo,
                        "descricao": descricao,
                        "ncm": ncm,
                        "cfop": cfop,
                        "unidade": uCom,
                        "quantidade": float(qCom),
                        "valor_unitario": float(vUnCom),
                        "valor_total": float(vProd),
                        
                        # Campos Específicos
                        "lote": lote_xml,
                        "validade": dVal_xml,
                        "fabricacao": dFab_xml,
                        "embalagem": embalagem_global, # Sugere a do transporte
                        
                        # Campos Arma
                        "seriais_xml": seriais_str,
                        "tpArma": tpArma_ref,
                        "nCano": nCano_ref,
                        "descricao_arma": descr_arma_ref,
                        
                        # Campos Extras (Veículo, etc - placeholders)
                        "marca": "", 
                        "modelo": "",
                        "calibre": "",
                    }
                    dados["itens"].append(item)

                return dados

            except Exception as e:
                _dlog(f"Erro LXML: {e}")
                # Se falhar, cai para o Fallback ElementTree abaixo
                pass
        
        # ==================================================
        # 2. FALLBACK ELEMENT TREE (Se LXML não estiver instalado ou falhar)
        # ==================================================
        raiz = ET.fromstring(xml_content)
        # Remove namespaces para facilitar o find()
        _strip_ns_etree(raiz)

        info_nf = (raiz.find(".//infNFe") or raiz.find(".//NFe/infNFe") or raiz.find(".//nfeProc/NFe/infNFe"))
        
        if info_nf is None:
             return {"success": False, "error": "Estrutura do XML inválida ou não suportada."}

        # (Lógica simplificada do ET para brevidade, mas funcional)
        # ... Chave, Número, Emitente ...
        chave_attr = (info_nf.attrib.get("Id") or "").strip()
        dados["chave"] = _normalize_chave(chave_attr)
        
        ide = info_nf.find(".//ide")
        if ide is not None:
            dados["numero"] = ide.findtext("nNF")
            dados["data_emissao"] = _parse_datetime_emi(ide.findtext("dhEmi"), ide.findtext("dEmi"))
        
        emit = info_nf.find(".//emit")
        if emit is not None:
            dados["fornecedor"] = emit.findtext("xNome")
            dados["cnpj_emit"] = _only_digits(emit.findtext("CNPJ"))

        # Itens via ET
        for det in info_nf.findall(".//det"):
            prod = det.find(".//prod")
            if prod is None: continue
            
            # Lote (Rastro)
            lote_txt = prod.findtext("lote") or ""
            if not lote_txt:
                rastro = prod.find(".//rastro")
                if rastro is not None:
                    lote_txt = rastro.findtext("nLote")
            
            # Seriais (Arma)
            seriais = []
            for arma in prod.findall(".//arma"):
                ns = arma.findtext("nSerie")
                if ns: seriais.append(ns)

            item = {
                "codigo_xml": prod.findtext("cProd"),
                "descricao": prod.findtext("xProd"),
                "quantidade": float(_to_decimal(prod.findtext("qCom"))),
                "valor_unitario": float(_to_decimal(prod.findtext("vUnCom"))),
                "lote": lote_txt,
                "seriais_xml": ",".join(seriais) if seriais else ""
            }
            item["valor_total"] = item["quantidade"] * item["valor_unitario"]
            dados["itens"].append(item)

        # ==================================================
        # 3. FALLBACK LLM (Último recurso)
        # ==================================================
        if not dados["itens"]:
            itens_llm = analisar_nf_xml_conteudo(xml_content)
            if itens_llm:
                dados["itens"] = itens_llm
                dados["valor_total"] = sum(i["quantidade"] * i["valor_unitario"] for i in itens_llm)
                return dados

        return dados

    except Exception as e:
        return {"success": False, "error": f"Erro fatal no parser: {e}"}