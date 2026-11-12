"""O cursor da NOVA (Modo Ajudante, 12/11/2026): uma janela transparente por
cima de tudo, que não pega clique, onde a setinha dela anda e clica.

    python -m jarvis.ajudante.cursor          (sobe sozinho quando a NOVA precisa)

O desenho e o movimento são os aprovados em vídeo pelo Léo:
- a setinha tem o MESMO formato do cursor do Linux dele (o tema do sistema,
  hoje o Bibata Modern), pintada no degradê da cor da persona, com borda
  branca, sombra macia e brilho; sem bolinha nenhuma;
- anda como gente: curva leve, acelera e freia (minimum-jerk), longe demora
  mais (Fitts), 15% mais rápido que a primeira versão;
- em todo clique, a onda de gota d'água (3 anéis que crescem e somem) e uma
  apertadinha.

O canal é um socket unix (uma linha JSON por pedido, uma por resposta):
    {"ir": [x, y]}                         anda até lá (responde quando chega)
    {"apontar": [x, y]}                    anda e faz a onda SEM clicar ("me mostra")
    {"clicar": [x, y], "botao": 1, "duplo": false}
    {"digitar": "texto"}  {"tecla": "ctrl+s"}  {"rolar": 3}
    {"cor": "#ff6fb5"}  {"esconder": true}  {"ping": true}
Coordenadas: as da tela inteira, em pixels reais.

Os cliques e teclas de verdade vão pelo XTest (X11). O ponteiro do Léo pula
pro lugar só no instante do clique e volta pra onde estava.
"""
from __future__ import annotations

import json
import math
import os
import socket
import struct
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from jarvis import canal

SOCKET = canal.pasta() / "jarvis-cursor.sock"
COR_PADRAO = "#4da3ff"


# ---------------------------------------------------------------------------
# A setinha: o cursor do tema do sistema, repintado na cor dela
# ---------------------------------------------------------------------------

def _tema_do_cursor() -> str:
    for chave in ("org.cinnamon.desktop.interface", "org.gnome.desktop.interface"):
        try:
            import subprocess
            r = subprocess.run(["gsettings", "get", chave, "cursor-theme"], capture_output=True, text=True, timeout=3)
            nome = r.stdout.strip().strip("'")
            if nome:
                return nome
        except Exception:
            pass
    return "Bibata-Modern-Classic"


def _ler_xcursor(caminho: Path) -> tuple[QImage, int, int] | None:
    """A maior imagem de um arquivo Xcursor, com a ponta (hotspot)."""
    try:
        b = caminho.read_bytes()
        n = struct.unpack_from("<I", b, 12)[0]
        melhor = None
        for i in range(n):
            tipo, _sub, pos = struct.unpack_from("<III", b, 16 + i * 12)
            if tipo == 0xfffd0002:
                _hl, _t, _s, _v, w, h, xh, yh, _d = struct.unpack_from("<IIIIIIIII", b, pos)
                if not melhor or w > melhor[1]:
                    melhor = (pos, w, h, xh, yh)
        pos, w, h, xh, yh = melhor
        img = QImage(b[pos + 36: pos + 36 + w * h * 4], w, h, QImage.Format_ARGB32).copy()
        return img, xh, yh
    except Exception:
        return None


def _seta_padrao() -> tuple[QImage, int, int]:
    """Sem tema legível: uma setinha arredondada desenhada aqui (preta com borda branca)."""
    from PySide6.QtGui import QPainterPath
    img = QImage(96, 96, QImage.Format_ARGB32); img.fill(Qt.transparent)
    p = QPainter(img); p.setRenderHint(QPainter.Antialiasing)
    c = QPainterPath(); c.moveTo(20, 8); c.lineTo(20, 74); c.quadTo(21, 80, 27, 76); c.lineTo(42, 62)
    c.quadTo(46, 58, 52, 58); c.lineTo(72, 58); c.quadTo(80, 57, 74, 50); c.lineTo(28, 6); c.quadTo(20, 0, 20, 8)
    p.setPen(QPen(Qt.white, 7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); p.setBrush(Qt.black); p.drawPath(c); p.end()
    return img, 20, 7


def seta_colorida(cor: str) -> tuple[QPixmap, float, float]:
    """A setinha na cor da persona: o preto vira degradê, o branco (borda) fica."""
    tema = _tema_do_cursor()
    achado = None
    for base in (Path.home() / ".icons", Path.home() / ".local/share/icons", Path("/usr/share/icons")):
        arq = base / tema / "cursors" / "left_ptr"
        if arq.exists():
            achado = _ler_xcursor(arq.resolve())
            if achado:
                break
    img, xh, yh = achado or _seta_padrao()
    img = img.convertToFormat(QImage.Format_ARGB32)
    c = QColor(cor)
    topo = [c.redF() + (1 - c.redF()) * 0.7, c.greenF() + (1 - c.greenF()) * 0.7, c.blueF() + (1 - c.blueF()) * 0.7]
    meio = [c.redF(), c.greenF(), c.blueF()]
    fundo = [v * 0.72 for v in meio]
    w, h = img.width(), img.height()
    for y in range(h):
        for x in range(w):
            px = img.pixelColor(x, y)
            if px.alpha() == 0:
                continue
            t = min(1.0, max(0.0, (x * 0.35 + y) / (w * 0.35 + h) * 1.25))
            a, b, k = (topo, meio, t / 0.45) if t < 0.45 else (meio, fundo, (t - 0.45) / 0.55)
            g = [a[i] + (b[i] - a[i]) * k for i in range(3)]
            claro = (px.redF() + px.greenF() + px.blueF()) / 3
            img.setPixelColor(x, y, QColor.fromRgbF(*(g[i] + (1 - g[i]) * claro for i in range(3)), px.alphaF()))
    return QPixmap.fromImage(img), float(xh), float(yh)


# ---------------------------------------------------------------------------
# As mãos de verdade (XTest)
# ---------------------------------------------------------------------------

class Maos:
    APELIDOS = {"ctrl": "Control_L", "control": "Control_L", "shift": "Shift_L", "alt": "Alt_L", "super": "Super_L",
                "enter": "Return", "esc": "Escape", "tab": "Tab", "backspace": "BackSpace", "delete": "Delete",
                "space": "space", "espaco": "space", "cima": "Up", "baixo": "Down", "esquerda": "Left",
                "direita": "Right", "home": "Home", "end": "End", "pageup": "Prior", "pagedown": "Next"}

    def __init__(self) -> None:
        from Xlib import X, XK, display
        from Xlib.ext import xtest
        self.X, self.XK, self.xtest = X, XK, xtest
        self.d = display.Display()

    def _kc(self, nome: str) -> int:
        nome = self.APELIDOS.get(nome.lower(), nome)
        s = self.XK.string_to_keysym(nome) or self.XK.string_to_keysym(nome.capitalize())
        if not s and len(nome) == 1:
            s = ord(nome)
        if not s:
            raise ValueError(f"tecla desconhecida: {nome}")
        return self.d.keysym_to_keycode(s)

    def _aperta(self, kc: int, baixo: bool) -> None:
        self.xtest.fake_input(self.d, self.X.KeyPress if baixo else self.X.KeyRelease, kc)
        self.d.sync()

    def tecla(self, combo: str) -> None:
        cods = [self._kc(p) for p in combo.replace(" ", "").split("+") if p]
        for kc in cods:
            self._aperta(kc, True)
        time.sleep(0.03)
        for kc in reversed(cods):
            self._aperta(kc, False)

    def _letra(self, ch: str) -> None:
        if ch == "\n":
            return self.tecla("Return")
        sym = ord(ch) if ord(ch) <= 0xff else 0x01000000 + ord(ch)
        kc = self.d.keysym_to_keycode(sym)
        if kc and self.d.keycode_to_keysym(kc, 0) == sym:
            self._aperta(kc, True); self._aperta(kc, False); return
        if kc and self.d.keycode_to_keysym(kc, 1) == sym:
            sh = self._kc("shift"); self._aperta(sh, True); self._aperta(kc, True); self._aperta(kc, False)
            self._aperta(sh, False); return
        # letra sem tecla (ç, ã...): empresta uma tecla vazia por um instante
        minimo = self.d.display.info.min_keycode
        mapa = self.d.get_keyboard_mapping(minimo, self.d.display.info.max_keycode - minimo + 1)
        vazio = next(minimo + i for i in range(len(mapa) - 1, -1, -1) if not any(mapa[i]))
        self.d.change_keyboard_mapping(vazio, [(sym,) * len(mapa[0])]); self.d.sync(); time.sleep(0.02)
        self._aperta(vazio, True); self._aperta(vazio, False); time.sleep(0.02)
        self.d.change_keyboard_mapping(vazio, [(0,) * len(mapa[0])]); self.d.sync()

    def digitar(self, texto: str) -> None:
        for ch in texto:
            self._letra(ch)
            time.sleep(0.012)

    def onde(self) -> tuple[int, int]:
        p = self.d.screen().root.query_pointer()
        return p.root_x, p.root_y

    def clicar(self, x: int, y: int, botao: int = 1, duplo: bool = False, voltar: bool = True) -> None:
        antes = self.onde()
        self.xtest.fake_input(self.d, self.X.MotionNotify, x=int(x), y=int(y)); self.d.sync()
        time.sleep(0.03)
        for _ in range(2 if duplo else 1):
            self.xtest.fake_input(self.d, self.X.ButtonPress, botao); self.d.sync()
            self.xtest.fake_input(self.d, self.X.ButtonRelease, botao); self.d.sync()
            time.sleep(0.05)
        if voltar:
            time.sleep(0.03)
            self.xtest.fake_input(self.d, self.X.MotionNotify, x=antes[0], y=antes[1]); self.d.sync()

    def rolar(self, vezes: int) -> None:
        b = 4 if vezes > 0 else 5
        for _ in range(abs(vezes)):
            self.xtest.fake_input(self.d, self.X.ButtonPress, b); self.d.sync()
            self.xtest.fake_input(self.d, self.X.ButtonRelease, b); self.d.sync()
            time.sleep(0.03)


# ---------------------------------------------------------------------------
# A janela transparente
# ---------------------------------------------------------------------------

def _suave(u: float) -> float:
    return u * u * u * (u * (6 * u - 15) + 10)


class Tela(QWidget):
    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.X11BypassWindowManagerHint
                         | Qt.WindowTransparentForInput | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        area = QRectF()
        for s in QGuiApplication.screens():
            area = area.united(QRectF(s.geometry()))
        self.setGeometry(area.toRect())
        self.origem = area.topLeft()
        self.cor(COR_PADRAO)
        self.pos = QPointF(area.center())
        self.anim = None                 # (ini, dur, de, para, controle, evento)
        self.ondas: list[tuple[float, QPointF]] = []
        self.aperto_ate = 0.0
        self.parado_desde = time.monotonic()
        self.relogio = QTimer(self)
        self.relogio.setInterval(16)
        self.relogio.timeout.connect(self._passo)

    def cor(self, hexa: str) -> None:
        self.hexa = hexa
        self.seta, self.hx, self.hy = seta_colorida(hexa)
        self.brilho = QColor(hexa)
        self.update()

    def ir(self, x: float, y: float, evento: threading.Event) -> None:
        para = QPointF(x, y) - self.origem
        de = QPointF(self.pos)
        dist = math.hypot(para.x() - de.x(), para.y() - de.y())
        dur = (18 + dist / 38) / 1.15 / 30          # o tempo do vídeo aprovado
        controle = QPointF((de.x() + para.x()) / 2 + (para.y() - de.y()) * 0.18,
                           (de.y() + para.y()) / 2 - (para.x() - de.x()) * 0.12)
        self.anim = (time.monotonic(), max(0.12, dur), de, para, controle, evento)
        self._acordar()

    def onda(self, x: float, y: float) -> None:
        self.ondas.append((time.monotonic(), QPointF(x, y) - self.origem))
        self.aperto_ate = time.monotonic() + 0.33
        self._acordar()

    def esconder(self) -> None:
        self.hide(); self.relogio.stop()

    def _acordar(self) -> None:
        if not self.isVisible():
            self.show()
        self.parado_desde = time.monotonic()
        if not self.relogio.isActive():
            self.relogio.start()

    def _passo(self) -> None:
        agora = time.monotonic()
        if self.anim:
            ini, dur, de, para, ctl, evento = self.anim
            u = min(1.0, (agora - ini) / dur)
            s = _suave(u); w = 1 - s
            self.pos = QPointF(w * w * de.x() + 2 * w * s * ctl.x() + s * s * para.x(),
                               w * w * de.y() + 2 * w * s * ctl.y() + s * s * para.y())
            if u >= 1:
                self.anim = None
                evento.set()
            self.parado_desde = agora
        self.ondas = [o for o in self.ondas if agora - o[0] < 1.4]
        if self.ondas or agora < self.aperto_ate:
            self.parado_desde = agora
        self.update()
        # Parada há 20 s: some (e o relógio para; nada gasta à toa).
        if agora - self.parado_desde > 20:
            self.esconder()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        agora = time.monotonic()
        c = QColor(self.hexa)
        for t0, ponto in self.ondas:
            f = (agora - t0) * 30
            if f < 6:
                cc = QColor(c); cc.setAlphaF(0.45 * (1 - f / 6)); p.setPen(Qt.NoPen); p.setBrush(cc)
                p.drawEllipse(ponto, 5 + f * 1.2, 5 + f * 1.2)
            for k in range(3):
                t = (f - k * 5) / 26
                if t <= 0 or t > 1:
                    continue
                r = 6 + 58 * (1 - (1 - t) ** 2.2)
                cc = QColor(c); cc.setAlphaF((1 - t) * (0.95 if k == 0 else 0.6))
                p.setPen(QPen(cc, 3.2 * (1 - t) + 0.4)); p.setBrush(Qt.NoBrush)
                p.drawEllipse(ponto, r, r * 0.92)
        aperto = 1.0
        resta = self.aperto_ate - agora
        if resta > 0:
            d = (0.33 - resta) * 30
            aperto = 1 - 0.14 * math.sin(math.pi * min(1, max(0, d / 10)))
        k = 0.44 * aperto
        p.translate(self.pos)
        p.scale(k, k)
        p.translate(-self.hx, -self.hy)
        # brilho e sombra: a mesma seta, maior e transparente, por baixo
        for dx, dy, cor, alfa, cresce in ((0, 6, QColor(0, 0, 0), 0.30, 1.06), (0, 0, c, 0.35, 1.12)):
            p.save(); p.setOpacity(alfa)
            p.translate(self.seta.width() / 2 + dx, self.seta.height() / 2 + dy); p.scale(cresce, cresce)
            p.translate(-self.seta.width() / 2, -self.seta.height() / 2)
            sombra = QPixmap(self.seta.size()); sombra.fill(Qt.transparent)
            q = QPainter(sombra); q.drawPixmap(0, 0, self.seta); q.setCompositionMode(QPainter.CompositionMode_SourceIn)
            q.fillRect(sombra.rect(), cor); q.end()
            p.drawPixmap(0, 0, sombra); p.restore()
        p.drawPixmap(0, 0, self.seta)
        p.end()


# ---------------------------------------------------------------------------
# O canal
# ---------------------------------------------------------------------------

class Ponte(QObject):
    pedir = Signal(dict, object)        # pedido, evento de resposta


def servir() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    tela = Tela()
    maos = Maos()
    ponte = Ponte()

    def no_qt(pedido: dict, ev) -> None:
        if "cor" in pedido:
            tela.cor(pedido["cor"]); ev.set()
        elif "esconder" in pedido:
            tela.esconder(); ev.set()
        elif "ir" in pedido:
            tela.ir(*pedido["ir"], ev)
        elif "onda" in pedido:
            tela.onda(*pedido["onda"]); ev.set()
        else:
            ev.set()
    ponte.pedir.connect(no_qt)

    def pedir_no_qt(pedido: dict, espera: float = 5.0) -> None:
        ev = threading.Event()
        ponte.pedir.emit(pedido, ev)
        ev.wait(espera)

    def atender(conexao: socket.socket) -> None:
        with conexao, conexao.makefile("rwb") as f:
            for linha in f:
                try:
                    pedido = json.loads(linha)
                    if "ping" in pedido:
                        pass
                    elif "ir" in pedido:
                        pedir_no_qt({"ir": pedido["ir"]})
                    elif "apontar" in pedido:
                        pedir_no_qt({"ir": pedido["apontar"]}); pedir_no_qt({"onda": pedido["apontar"]})
                        time.sleep(0.45)
                    elif "clicar" in pedido:
                        x, y = pedido["clicar"]
                        pedir_no_qt({"ir": [x, y]})
                        time.sleep(0.05)
                        pedir_no_qt({"onda": [x, y]})
                        maos.clicar(x, y, int(pedido.get("botao", 1)), bool(pedido.get("duplo")))
                        time.sleep(0.2)
                    elif "digitar" in pedido:
                        maos.digitar(str(pedido["digitar"]))
                    elif "tecla" in pedido:
                        maos.tecla(str(pedido["tecla"]))
                    elif "rolar" in pedido:
                        maos.rolar(int(pedido["rolar"]))
                    else:
                        pedir_no_qt(pedido)
                    f.write(b'{"ok": true}\n')
                except Exception as e:  # noqa: BLE001 - o erro volta pra quem pediu
                    f.write((json.dumps({"ok": False, "erro": str(e)}) + "\n").encode())
                f.flush()

    if SOCKET.exists():
        SOCKET.unlink()
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(str(SOCKET)); os.chmod(SOCKET, 0o600); srv.listen(4)

    def aceitar() -> None:
        while True:
            c, _ = srv.accept()
            threading.Thread(target=atender, args=(c,), daemon=True).start()
    threading.Thread(target=aceitar, daemon=True).start()
    print(f"cursor da NOVA pronto: {SOCKET}", flush=True)
    return app.exec()


if __name__ == "__main__":
    sys.exit(servir())
