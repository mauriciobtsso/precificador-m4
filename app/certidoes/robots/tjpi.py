# app/certidoes/robots/tjpi.py
"""
Robô de emissão da Certidão Unificada TJPI (europa.tjpi.jus.br/certidao/unificada).

Fluxo (semi-automático, por causa do reCAPTCHA v2 real do Google):
    1. Abre o navegador (headless=False) na página do TJPI.
    2. Preenche todos os campos do formulário (Angular Material).
    3. PARA e espera alguém clicar no "não sou um robô" (e resolver o desafio
       de imagem, se aparecer) e clicar em "Emitir".
    4. Depois de submetido, espera o resultado (nova página / modal / download)
       e captura o PDF.
"""

import io
import re
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout, Page

TJPI_URL = "https://europa.tjpi.jus.br/certidao/unificada"


class TJPIRobotError(Exception):
    pass


@dataclass
class DadosRequerenteTJPI:
    nome: str
    cpf: str  
    rg: str
    orgao_expedidor: str
    estado_civil: str          
    mae: str
    cep: str                   
    endereco: str
    bairro: str
    uf: str                    
    municipio: str             
    pai: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    
    # Defaults ajustados com os nomes reais do portal
    tipo_pessoa: str = "PESSOA FÍSICA"
    grau_jurisdicao: str = "AMBAS"
    tipo_certidao: str = "Negativa Criminal e Auditoria Militar"


# --------------------------------------------------------
# Importação Resiliente do Playwright Stealth (Fail-Safe)
# --------------------------------------------------------
def _aplicar_stealth(page: Page):
    try:
        import playwright_stealth
        if hasattr(playwright_stealth, 'stealth_sync') and callable(playwright_stealth.stealth_sync):
            playwright_stealth.stealth_sync(page)
        elif hasattr(playwright_stealth, 'stealth') and callable(playwright_stealth.stealth):
            playwright_stealth.stealth(page)
        elif hasattr(playwright_stealth, 'stealth') and not callable(playwright_stealth.stealth):
            if hasattr(playwright_stealth.stealth, 'stealth') and callable(playwright_stealth.stealth.stealth):
                playwright_stealth.stealth.stealth(page)
    except Exception as e:
        print(f">>> AVISO: Falha ao injetar stealth ({e}). Prosseguindo sem camuflagem...")


def _selecionar_mat_select(page: Page, form_control_name: str, texto_opcao: str, timeout_ms: int = 5000):
    """
    Clica no select do Angular e busca a opção via Regex (imune a letras maiúsculas/minúsculas).
    """
    trigger = page.locator(f'mat-select[formcontrolname="{form_control_name}"]')
    trigger.wait_for(state="visible", timeout=timeout_ms)
    trigger.click(force=True)

    # Busca a opção no overlay do Angular Material
    opcao = page.locator("mat-option").filter(has_text=re.compile(texto_opcao, re.IGNORECASE)).first
    opcao.wait_for(state="visible", timeout=timeout_ms)
    opcao.click()


def _preencher_input(page: Page, form_control_name: str, valor: Optional[str]):
    """
    Clica no campo e digita tecla por tecla para humanizar a interação.
    """
    if not valor:
        return
    locator = page.locator(f'input[formcontrolname="{form_control_name}"]')
    locator.wait_for(state="visible", timeout=5000)
    locator.click()
    locator.press_sequentially(valor, delay=50)


def emitir_certidao_tjpi(dados: DadosRequerenteTJPI, timeout_captcha_segundos: int = 300) -> bytes:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = context.new_page()
        _aplicar_stealth(page)

        try:
            page.goto(TJPI_URL, wait_until="networkidle")

            # --------------------------------------------------------
            # TRAVA DE SEGURANÇA: Espera a página realmente carregar
            # Garante que o formulário está visível antes de tentar clicar
            # --------------------------------------------------------
            page.wait_for_selector('mat-select[formcontrolname="tipoParte"]', state="visible", timeout=15000)

            # --------------------------------------------------------
            # Selects (Angular Material)
            # --------------------------------------------------------
            _selecionar_mat_select(page, "tipoParte", dados.tipo_pessoa)
            _selecionar_mat_select(page, "grauJuridicao", dados.grau_jurisdicao)
            _selecionar_mat_select(page, "tipoCertidao", dados.tipo_certidao)
            _selecionar_mat_select(page, "estadoCivil", dados.estado_civil)

            # --------------------------------------------------------
            # Campos de texto simples
            # --------------------------------------------------------
            _preencher_input(page, "requerente", dados.nome)
            _preencher_input(page, "cpf", dados.cpf)
            _preencher_input(page, "rg", dados.rg)
            _preencher_input(page, "orgaoExpedidor", dados.orgao_expedidor)
            _preencher_input(page, "pai", dados.pai)
            _preencher_input(page, "mae", dados.mae)
            
            # --------------------------------------------------------
            # Automação Inteligente do CEP
            # --------------------------------------------------------
            cep_locator = page.locator('input[formcontrolname="cep"]')
            cep_locator.click()
            cep_locator.press_sequentially(dados.cep, delay=100)
            cep_locator.press("Tab") # Dispara a busca do TJPI
            
            # Espera a API do TJPI carregar Bairro, Rua e Cidade
            page.wait_for_timeout(2500)
            
            # Preenche apenas o que ficou faltando
            _preencher_input(page, "numero", dados.numero)
            _preencher_input(page, "complemento", dados.complemento)

            print(">>> Robô TJPI: formulário preenchido inteligentemente via CEP.")
            print(">>> Resolva o reCAPTCHA (clique em 'não sou um robô' e, se pedir, "
                  "o desafio de imagens) e clique em 'Emitir'.")

            # --------------------------------------------------------
            # Espera submissão (intervenção humana)
            # --------------------------------------------------------
            with page.expect_navigation(timeout=timeout_captcha_segundos * 1000):
                pass  

            # Placeholder para capturar o PDF que resolveremos na próxima etapa
            raise TJPIRobotError(
                "Formulário submetido com sucesso, mas a captura do PDF final "
                "ainda não está implementada — preciso ver o HTML da página de "
                "resultado (depois do captcha) para fechar essa parte."
            )

        except PlaywrightTimeout:
            raise TJPIRobotError(
                f"Timeout esperando resolução do captcha/submissão ({timeout_captcha_segundos}s)."
            )
        finally:
            browser.close()