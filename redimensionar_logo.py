"""
Redimensiona o logo da M4 Tática para o tamanho correto de exibição.

Uso:
    python redimensionar_logo.py

O arquivo de entrada deve ser: app/static/img/logo.webp (ou logo.png)
O arquivo de saída será:       app/static/img/logo.webp (sobrescreve)

Tamanho de exibição no site:
  - Desktop: 160 x 55px  (CSS: width:160px, height:55px)
  - Mobile:  120 x 40px  (CSS: width:120px, height:40px)

Geramos em 2x para telas retina: 320 x 110px
Isso reduz de ~21 KiB para ~2-3 KiB mantendo nitidez em todos os dispositivos.
"""

from PIL import Image
import os

INPUT  = os.path.join('app', 'static', 'img', 'logo.webp')
# Tenta PNG se WebP não existir
if not os.path.exists(INPUT):
    INPUT = os.path.join('app', 'static', 'img', 'logo.png')

OUTPUT = os.path.join('app', 'static', 'img', 'logo.webp')

# 2x do tamanho de exibição máximo (160x55) = 320x110
TARGET_W = 320
TARGET_H = 110

with Image.open(INPUT) as img:
    print(f"Tamanho original: {img.size[0]}x{img.size[1]}px")

    # Converte para RGBA para preservar transparência (logos geralmente têm fundo transparente)
    if img.mode not in ('RGBA', 'RGB'):
        img = img.convert('RGBA')

    # Redimensiona mantendo proporção dentro de 320x110
    img.thumbnail((TARGET_W, TARGET_H), Image.LANCZOS)

    print(f"Novo tamanho:     {img.size[0]}x{img.size[1]}px")

    img.save(OUTPUT, 'WEBP', quality=85, method=6)

original_kb = os.path.getsize(INPUT) / 1024
output_kb   = os.path.getsize(OUTPUT) / 1024
print(f"Tamanho antes:    {original_kb:.1f} KiB")
print(f"Tamanho depois:   {output_kb:.1f} KiB")
print(f"Economia:         {original_kb - output_kb:.1f} KiB ({(1 - output_kb/original_kb)*100:.0f}%)")
print(f"\nSalvo em: {OUTPUT}")