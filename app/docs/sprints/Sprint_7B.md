\# Sprint 7B — Importação de NF-e de Compras



\### 🧠 Objetivo

Implementar o parser híbrido de NF-e (CBC, Taurus, Pavei) com leitura XML avançada e persistência via AJAX.



\### ⚙️ Alterações

\- \*\*`utils.py`\*\*: parser robusto (`lxml` + ET fallback), tratamento de duplicidade CBC.

\- \*\*`routes.py`\*\*: integração com endpoint `/compras/salvar`.

\- \*\*`compras\_importar.js`\*\*: frontend AJAX modular.

\- \*\*`importar.html`\*\*: layout clean, responsivo e integrado.

\- \*\*`requirements.txt`\*\*: adicionada dependência `lxml==5.3.0`.



\### ✅ Testado com

\- CBC Brasil (arma 7022)

\- Pavei Brasil (pistola G2C)

\- XML Taurus (arma G3C)



