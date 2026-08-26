from pathlib import Path
import re

project = Path(__file__).resolve().parents[1]
source = project / "app/static/vendor/bootstrap-icons/bootstrap-icons.css"
target = project / "app/static/vendor/bootstrap-icons/bootstrap-icons-loja.css"
used = set(re.findall(r"bi-[a-z0-9-]+", "\n".join(str(p.read_text(errors='ignore')) for p in (project / "app/loja/templates").rglob("*.html"))))
used.update(re.findall(r"bi-[a-z0-9-]+", (project / "app/static/js/cart-handler.js").read_text(errors="ignore")))
css = source.read_text(errors="ignore")
font_block = css[css.index("@font-face"):css.index(".bi::before,")]
base_end = css.index("}\n", css.index(".bi::before,")) + 2
base_block = css[css.index(".bi::before,"):base_end]
icon_rules = []
for name in sorted(used):
    match = re.search(rf"^\.{re.escape(name)}::before \{{[^}}]+\}}", css, re.MULTILINE)
    if match:
        icon_rules.append(match.group(0))
    else:
        raise SystemExit(f"Ícone não encontrado na folha original: {name}")
target.write_text(
    "/*! Bootstrap Icons subset for the public M4 Tática storefront. */\n"
    + font_block + base_block + "\n" + "\n".join(icon_rules) + "\n",
    encoding="utf-8",
)
print(f"Gerado {target} com {len(icon_rules)} ícones.")
