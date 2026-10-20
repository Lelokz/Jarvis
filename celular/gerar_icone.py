"""Gera o ícone do app (o átomo do Jarvis com o anel de HUD), em dois formatos
do MESMO desenho: SVG (para ver a prévia no PC) e VectorDrawable (o Android).

    python3 celular/gerar_icone.py [pasta-da-previa]

Escreve app/src/main/res/drawable/ic_frente.xml e ic_fundo.xml. Coordenadas
em 108x108 (o ícone adaptativo); o launcher mostra o meio, raio ~36.
"""
import math
import sys
from pathlib import Path

C = 54.0
AZUL, CLARO, ROXO = "#4DA3FF", "#7CC4FF", "#9B7BFF"
ANEIS = [(0, AZUL), (60, CLARO), (120, ROXO)]   # inclinação, cor
RX, RY = 27.0, 9.5


def ponto(ang, x, y):
    """Gira (x, y) em volta do centro: o VectorDrawable não tem transform em
    path, então os pontos já saem girados."""
    a = math.radians(ang)
    dx, dy = x - C, y - C
    return C + dx * math.cos(a) - dy * math.sin(a), C + dx * math.sin(a) + dy * math.cos(a)


def meia_elipse(ang, frente):
    # Metade de trás = a de cima (passa atrás do núcleo); da frente = a de baixo.
    (x0, y0), (x1, y1) = (ponto(ang, C + RX, C), ponto(ang, C - RX, C)) if frente else \
                         (ponto(ang, C - RX, C), ponto(ang, C + RX, C))
    return f"M{x0:.2f},{y0:.2f} A{RX},{RY} {ang} 0 1 {x1:.2f},{y1:.2f}"


def eletron(ang, x):
    y = C + RY * math.sqrt(1 - ((x - C) / RX) ** 2)
    return ponto(ang, x, y)


def circulo(cx, cy, r):
    return (f"M{cx - r:.2f},{cy:.2f} a{r:.2f},{r:.2f} 0 1 0 {2 * r:.2f},0 "
            f"a{r:.2f},{r:.2f} 0 1 0 {-2 * r:.2f},0 Z")


def tracos_hud():
    """O anel de HUD: marcas em volta, mais compridas a cada 45°."""
    partes = []
    for i in range(48):
        ang = i * 7.5
        if 20 < ang % 90 < 70 and i % 2:   # falhas no anel, como no HUD do filme
            continue
        longo = i % 6 == 0
        r0, r1 = (31.5, 34.5) if longo else (32.6, 34.0)
        a = math.radians(ang)
        partes.append(f"M{C + r0 * math.cos(a):.2f},{C + r0 * math.sin(a):.2f} "
                      f"L{C + r1 * math.cos(a):.2f},{C + r1 * math.sin(a):.2f}")
    return " ".join(partes)


ELETRONS = [eletron(0, 65), eletron(60, 38), eletron(120, 72)]
POEIRA = [(33, 36, .7, .7), (78, 33, .6, .6), (82, 72, .7, .5), (30, 74, .6, .6),
          (46, 28, .5, .5), (66, 82, .5, .5), (24, 50, .45, .4), (85, 56, .45, .4)]


def svg():
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108"><defs>',
         '<radialGradient id="f" cx="54" cy="50" r="62" gradientUnits="userSpaceOnUse">'
         '<stop offset="0" stop-color="#16243A"/><stop offset="0.55" stop-color="#0D131C"/>'
         '<stop offset="1" stop-color="#07090D"/></radialGradient>',
         '<radialGradient id="h" cx="54" cy="54" r="34" gradientUnits="userSpaceOnUse">'
         '<stop offset="0" stop-color="#4DA3FF" stop-opacity="0.35"/>'
         '<stop offset="1" stop-color="#4DA3FF" stop-opacity="0"/></radialGradient>',
         '<radialGradient id="n" cx="54" cy="54" r="13" gradientUnits="userSpaceOnUse">'
         '<stop offset="0" stop-color="#FFFFFF"/><stop offset="0.25" stop-color="#BFE1FF"/>'
         '<stop offset="0.6" stop-color="#4DA3FF" stop-opacity="0.85"/>'
         '<stop offset="1" stop-color="#4DA3FF" stop-opacity="0"/></radialGradient></defs>',
         '<rect width="108" height="108" fill="url(#f)"/>']
    s += corpo_svg()
    return "\n".join(s + ["</svg>"])


def corpo_svg():
    s = ['<circle cx="54" cy="54" r="34" fill="url(#h)"/>',
         f'<path d="{tracos_hud()}" stroke="#4DA3FF" stroke-opacity="0.45" stroke-width="0.7" '
         'stroke-linecap="round" fill="none"/>',
         f'<path d="{circulo(C, C, 30)}" stroke="#4DA3FF" stroke-opacity="0.18" stroke-width="0.5" fill="none"/>']
    for ang, cor in ANEIS:
        s.append(f'<path d="{meia_elipse(ang, False)}" stroke="{cor}" stroke-opacity="0.38" '
                 'stroke-width="1.6" fill="none" stroke-linecap="round"/>')
    s.append(f'<path d="{circulo(C, C, 10.5)}" fill="#0A0C10"/>')
    s.append(f'<path d="{circulo(C, C, 13)}" fill="url(#n)"/>')
    for ang, cor in ANEIS:
        s.append(f'<path d="{meia_elipse(ang, True)}" stroke="{cor}" stroke-width="2.4" '
                 'fill="none" stroke-linecap="round"/>')
    for x, y in ELETRONS:
        s.append(f'<path d="{circulo(x, y, 3.2)}" fill="#4DA3FF" fill-opacity="0.35"/>')
        s.append(f'<path d="{circulo(x, y, 1.7)}" fill="#FFFFFF"/>')
    for x, y, r, o in POEIRA:
        s.append(f'<path d="{circulo(x, y, r)}" fill="#9FD3FF" fill-opacity="{o}"/>')
    return s


def gradiente(cx, cy, r, paradas):
    itens = "".join(f'<item android:offset="{o}" android:color="{c}"/>' for o, c in paradas)
    return (f'<aapt:attr name="android:fillColor"><gradient android:type="radial" '
            f'android:centerX="{cx}" android:centerY="{cy}" android:gradientRadius="{r}">'
            f'{itens}</gradient></aapt:attr>')


def vetor(conteudo):
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<!-- Gerado por celular/gerar_icone.py: mude lá, não aqui. -->\n'
            '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
            '    xmlns:aapt="http://schemas.android.com/aapt"\n'
            '    android:width="108dp" android:height="108dp"\n'
            '    android:viewportWidth="108" android:viewportHeight="108">\n'
            + conteudo + '</vector>\n')


def caminho(d, **a):
    attrs = " ".join(f'android:{k}="{v}"' for k, v in a.items())
    return f'    <path android:pathData="{d}" {attrs}/>\n'


def frente_xml():
    x = ""
    x += (f'    <path android:pathData="{circulo(C, C, 34)}">'
          + gradiente(54, 54, 34, [(0, "#594DA3FF"), (1, "#004DA3FF")]) + '</path>\n')
    x += caminho(tracos_hud(), strokeColor="#4DA3FF", strokeAlpha="0.45", strokeWidth="0.7",
                 strokeLineCap="round")
    x += caminho(circulo(C, C, 30), strokeColor="#4DA3FF", strokeAlpha="0.18", strokeWidth="0.5")
    for ang, cor in ANEIS:
        x += caminho(meia_elipse(ang, False), strokeColor=cor, strokeAlpha="0.38", strokeWidth="1.6",
                     strokeLineCap="round")
    x += caminho(circulo(C, C, 10.5), fillColor="#0A0C10")
    x += (f'    <path android:pathData="{circulo(C, C, 13)}">'
          + gradiente(54, 54, 13, [(0, "#FFFFFFFF"), (0.25, "#FFBFE1FF"), (0.6, "#D94DA3FF"),
                                   (1, "#004DA3FF")]) + '</path>\n')
    for ang, cor in ANEIS:
        x += caminho(meia_elipse(ang, True), strokeColor=cor, strokeWidth="2.4", strokeLineCap="round")
    for ex, ey in ELETRONS:
        x += caminho(circulo(ex, ey, 3.2), fillColor="#4DA3FF", fillAlpha="0.35")
        x += caminho(circulo(ex, ey, 1.7), fillColor="#FFFFFF")
    for px, py, r, o in POEIRA:
        x += caminho(circulo(px, py, r), fillColor="#9FD3FF", fillAlpha=str(o))
    return vetor(x)


def fundo_xml():
    return vetor(f'    <path android:pathData="M0,0h108v108h-108z">'
                 + gradiente(54, 50, 62, [(0, "#FF16243A"), (0.55, "#FF0D131C"), (1, "#FF07090D")])
                 + '</path>\n')


if __name__ == "__main__":
    res = Path(__file__).parent / "app/src/main/res/drawable"
    (res / "ic_frente.xml").write_text(frente_xml())
    (res / "ic_fundo.xml").write_text(fundo_xml())
    if len(sys.argv) > 1:
        Path(sys.argv[1], "icone.svg").write_text(svg())
    print("ok")
