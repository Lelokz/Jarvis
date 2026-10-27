"""O ícone do átomo da NOVA, desenhado (e não uma foto do 3D).

A foto do 3D, reduzida, virava uma bola com círculos grudados: a câmera em
perspectiva e o brilho embolam tudo. Aqui o átomo é montado para ser lido
pequeno, numa pose escolhida:
- as três argolas a 0°, 60° e 120°, inclinadas por igual, com o formato de
  cada uma (a externa larga em 3 partes, a interna tracejada, a do meio com
  pontos de luz) quando há espaço para isso;
- a metade de trás de cada argola passa atrás do núcleo e a da frente passa
  na frente, com um corte em volta (como num nó), para dar profundidade;
- uma bolinha por argola, na ponta da frente, com o rastro afinando atrás;
- o núcleo com a casca geodésica (só nos grandes) e a borda acesa.

    .venv/bin/python arte/icone_atomo.py SAIDA.png --cor 4da3ff --lado 256
"""

from __future__ import annotations

import argparse
import math

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen, QRadialGradient

INCLINA = 0.34          # quanto as argolas achatam (cos da inclinação)
NUCLEO = 0.25           # raio do núcleo (o átomo inteiro tem raio 1)
# raio maior, largura do traço (em fração do lado) e onde fica a bolinha
ARGOLAS = [
    dict(raio=0.96, larg=0.034, bola=0.16),
    dict(raio=0.80, larg=0.022, bola=0.86, sentido=-1),   # do outro lado, girando ao contrário (como no 3D)
    dict(raio=0.88, larg=0.026, bola=0.13, alonga=1.08),
]


def _clara(cor: QColor, k: float) -> QColor:
    return QColor.fromRgbF(cor.redF() + (1 - cor.redF()) * k, cor.greenF() + (1 - cor.greenF()) * k, cor.blueF() + (1 - cor.blueF()) * k)


def _icosaedro():
    """Vértices e arestas de um icosaedro subdividido uma vez (a casca geodésica)."""
    f = (1 + 5 ** 0.5) / 2
    v = [(-1, f, 0), (1, f, 0), (-1, -f, 0), (1, -f, 0), (0, -1, f), (0, 1, f), (0, -1, -f), (0, 1, -f), (f, 0, -1), (f, 0, 1), (-f, 0, -1), (-f, 0, 1)]
    v = [np.array(p, float) / np.linalg.norm(p) for p in v]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
             (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    meio = {}

    def m(a, b):
        k = (min(a, b), max(a, b))
        if k not in meio:
            p = v[a] + v[b]
            v.append(p / np.linalg.norm(p))
            meio[k] = len(v) - 1
        return meio[k]
    arestas = set()
    for a, b, c in faces:
        ab, bc, ca = m(a, b), m(b, c), m(c, a)
        for t in ((a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)):
            for i in range(3):
                x, y = t[i], t[(i + 1) % 3]
                arestas.add((min(x, y), max(x, y)))
    return np.array(v), sorted(arestas)


GEO = _icosaedro()


def desenhar(lado: int, cor: QColor | str = "#4da3ff", branco: bool = False) -> QImage:
    """O ícone em `lado` px, fundo transparente. `branco`: só a silhueta (notificação do Android)."""
    cor = QColor(cor)
    if branco:
        cor = QColor("#ffffff")
    img = QImage(lado, lado, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    c = lado / 2
    k = lado / 2 * (0.9 if lado >= 64 else 0.97)   # raio 1 do átomo (com folga para o brilho, nos grandes)
    minusculo = lado < 24         # 16 px: sem rastro, o núcleo aceso por inteiro
    detalhe = lado >= 96          # formatos das argolas e casca geodésica
    medio = lado >= 40            # cortes de profundidade
    grosso = 1.6 if lado < 40 else 1.0   # pequeno, o traço engrossa para não sumir
    px = lambda f: max(f * lado * grosso, 1.3 if lado < 24 else 1.5)
    clara = _clara(cor, 0.55)

    def ponto(i, a, t):
        A = ARGOLAS[i]
        rx, ry = A["raio"] * A.get("alonga", 1), A["raio"] * INCLINA / A.get("alonga", 1)
        x, y = math.cos(t) * rx, math.sin(t) * ry
        fi = i * math.pi / 3 - math.pi / 6
        return QPointF(c + k * (x * math.cos(fi) - y * math.sin(fi)), c + k * (x * math.sin(fi) + y * math.cos(fi)))

    def caminho(i, t0, t1, n=120):
        path = QPainterPath(ponto(i, None, t0))
        for j in range(1, n + 1):
            path.lineTo(ponto(i, None, t0 + (t1 - t0) * j / n))
        return path

    def argola(i, frente):
        """Metade da frente (t de 0 a π) ou de trás (π a 2π), no formato da argola."""
        A = ARGOLAS[i]
        t0 = 0 if frente else math.pi
        w = px(A["larg"])
        tom = cor if frente else QColor.fromRgbF(cor.redF(), cor.greenF(), cor.blueF(), 0.55)
        partes = [(t0, t0 + math.pi)]
        if detalhe and i == 0:   # a externa: 3 partes com vãos
            vao = 0.10
            partes = []
            for s in range(3):
                a0, a1 = s * 2 * math.pi / 3 + vao / 2 + 0.4, (s + 1) * 2 * math.pi / 3 - vao / 2 + 0.4
                lo, hi = max(a0, t0), min(a1, t0 + math.pi)
                if lo < hi:
                    partes.append((lo, hi))
                lo, hi = max(a0 - 2 * math.pi, t0), min(a1 - 2 * math.pi, t0 + math.pi)
                if lo < hi:
                    partes.append((lo, hi))
        for a0, a1 in partes:
            path = caminho(i, a0, a1)
            if frente and medio:   # o corte: some o que está atrás, em volta do traço
                p.setCompositionMode(QPainter.CompositionMode_Clear)
                p.strokePath(path, QPen(Qt.black, w + px(0.022), Qt.SolidLine, Qt.RoundCap))
                p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            if detalhe and i == 0:   # faixa larga: corpo fraco e as duas bordas acesas
                p.strokePath(path, QPen(QColor.fromRgbF(tom.redF(), tom.greenF(), tom.blueF(), tom.alphaF() * 0.35), w * 1.9, Qt.SolidLine, Qt.FlatCap))
                for lado_borda in (-1, 1):
                    q = QPainterPath()
                    pts = [path.pointAtPercent(j / 120) for j in range(121)]
                    for j, pt in enumerate(pts):
                        a = pts[max(j - 1, 0)]
                        b = pts[min(j + 1, 120)]
                        dx, dy = b.x() - a.x(), b.y() - a.y()
                        n = math.hypot(dx, dy) or 1
                        o = QPointF(pt.x() - dy / n * w * 0.8 * lado_borda, pt.y() + dx / n * w * 0.8 * lado_borda)
                        q.moveTo(o) if j == 0 else q.lineTo(o)
                    p.strokePath(q, QPen(tom, w * 0.42, Qt.SolidLine, Qt.FlatCap))
            elif detalhe and i == 1:  # a interna: tracejada
                pen = QPen(tom, w, Qt.CustomDashLine, Qt.FlatCap)
                pen.setDashPattern([2.2, 1.4])
                p.strokePath(path, pen)
            else:
                p.strokePath(path, QPen(tom, w, Qt.SolidLine, Qt.RoundCap))
            if detalhe and i == 2:   # a do meio: pontos de luz
                p.setPen(Qt.NoPen)
                p.setBrush(clara)
                for j in range(12):
                    t = j * 2 * math.pi / 12 + 0.26
                    if a0 <= t <= a1 or a0 <= t - 2 * math.pi <= a1:
                        p.drawEllipse(ponto(i, None, t), w * 0.6, w * 0.6)

    def bolinha(i):
        A = ARGOLAS[i]
        t = A["bola"] * math.pi
        # o rastro: um arco atrás da bolinha, afinando e apagando
        n = 0 if minusculo else 26
        comp = 1.3
        r = px(0.038 if lado >= 40 else 0.034)
        for j in range(n):
            s = A.get("sentido", 1)
            a, b = t - s * comp * (1 - j / n), t - s * comp * (1 - (j + 1) / n)
            f = (j + 1) / n
            seg = QPainterPath(ponto(i, None, a))
            seg.lineTo(ponto(i, None, b))
            col = QColor.fromRgbF(clara.redF(), clara.greenF(), clara.blueF(), f ** 1.6)
            p.strokePath(seg, QPen(col, max(r * 1.3 * (0.25 + 0.75 * f), 0.8), Qt.SolidLine, Qt.RoundCap))
        o = ponto(i, None, t)
        if medio:
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.setPen(Qt.NoPen)
            p.setBrush(Qt.black)
            p.drawEllipse(o, r + px(0.016), r + px(0.016))
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        g = QRadialGradient(o, r)
        g.setColorAt(0, QColor("#ffffff"))
        g.setColorAt(0.55, _clara(cor, 0.75))
        g.setColorAt(1, clara)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(o, r, r)

    def nucleo():
        rn = k * NUCLEO
        centro = QPointF(c, c)
        if medio:   # o corte em volta do núcleo: as metades de trás somem atrás dele
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.setPen(Qt.NoPen)
            p.setBrush(Qt.black)
            p.drawEllipse(centro, rn + px(0.03), rn + px(0.03))
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        g = QRadialGradient(QPointF(c - rn * 0.3, c - rn * 0.35), rn * 1.25)
        if minusculo and not branco:
            g.setColorAt(0, _clara(cor, 0.6))
            g.setColorAt(1, cor)
        elif branco:
            g.setColorAt(0, QColor(255, 255, 255, 255))
            g.setColorAt(1, QColor(255, 255, 255, 200))
        else:
            g.setColorAt(0, _clara(cor, 0.35))
            g.setColorAt(0.55, QColor.fromRgbF(cor.redF() * 0.45, cor.greenF() * 0.45, cor.blueF() * 0.45))
            g.setColorAt(1, QColor.fromRgbF(cor.redF() * 0.22, cor.greenF() * 0.22, cor.blueF() * 0.22))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(centro, rn, rn)
        if detalhe and not branco:   # a casca geodésica: só as arestas da frente
            v, arestas = GEO
            rx, ry = 0.5, 0.35
            R = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]]) @ \
                np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
            w3 = v @ R.T
            for a, b in arestas:
                z = (w3[a, 2] + w3[b, 2]) / 2
                if z < 0.05:
                    continue
                col = QColor.fromRgbF(cor.redF(), cor.greenF(), cor.blueF(), 0.25 + 0.5 * z)
                p.setPen(QPen(col, max(lado / 300, 0.8)))
                p.drawLine(QPointF(c + w3[a, 0] * rn, c - w3[a, 1] * rn), QPointF(c + w3[b, 0] * rn, c - w3[b, 1] * rn))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(clara, px(0.016)))
        p.drawEllipse(centro, rn, rn)

    for i in range(3):
        argola(i, False)
    nucleo()
    for i in range(3):
        argola(i, True)
    for i in range(3):
        bolinha(i)
    p.end()

    if not branco and lado >= 64:   # um brilho bem leve em volta (borrão por redução)
        brilho = img.scaled(max(lado // 10, 4), max(lado // 10, 4), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        brilho = brilho.scaled(lado, lado, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        final = QImage(lado, lado, QImage.Format_ARGB32_Premultiplied)
        final.fill(Qt.transparent)
        q = QPainter(final)
        q.setOpacity(0.5)
        q.drawImage(0, 0, brilho)
        q.setOpacity(1)
        q.drawImage(0, 0, img)
        q.end()
        img = final
    return img


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("saida")
    a.add_argument("--cor", default="4da3ff")
    a.add_argument("--lado", type=int, default=256)
    a.add_argument("--branco", action="store_true", help="só a silhueta branca (notificação do Android)")
    o = a.parse_args()
    app = QGuiApplication.instance() or QGuiApplication([])
    desenhar(o.lado, "#" + o.cor, o.branco).save(o.saida)
    print(o.saida)


if __name__ == "__main__":
    main()
