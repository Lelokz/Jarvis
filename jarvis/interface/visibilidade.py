"""A janela está sendo vista de verdade?

**Medido na prova de conceito da Etapa 6, e é o contrário do que eu supus:**
minimizada, o Cinnamon responde `visibility=Minimized` mas mantém
`exposed=True`, e o Qt continua desenhando a 60 fps. E, coberta por um jogo em
tela cheia, nada chega ao Qt: `visibility` segue `Windowed`, `exposed` segue
`True`, e o foco não serve de sinal — numa medição ele caiu cinco segundos
antes de o jogo aparecer.

Quem sabe a verdade é o gerenciador de janelas: a janela ativa tem a
propriedade `_NET_WM_STATE_FULLSCREEN`. Isso vem do X11 e não do Qt, então
valeria igual com qualquer outra ferramenta.

Para não disparar processo a cada segundo, escuta o `xprop -root -spy`, que
avisa quando a janela ativa MUDA, e só então pergunta o estado dela.
"""

from __future__ import annotations

import shutil
import subprocess
import threading

from PySide6.QtCore import QObject, Signal, Slot


class OlhoDeTelaCheia(QObject):
    """Emite `mudou(True)` quando uma tela cheia de OUTRO programa está na frente."""

    mudou = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._nossa_janela = 0
        self._na_frente = False
        self._parar = threading.Event()
        self._espia: subprocess.Popen | None = None
        self._thread = threading.Thread(target=self._laco, name="tela-cheia", daemon=True)

    @Slot(int)
    def definirJanela(self, identificador: int) -> None:
        self._nossa_janela = int(identificador)

    def iniciar(self) -> None:
        if shutil.which("xprop") is None:
            return  # sem xprop, a janela simplesmente não ganha este cuidado
        self._thread.start()

    def encerrar(self) -> None:
        self._parar.set()
        if self._espia is not None:
            self._espia.terminate()

    # ----------------------------------------------------------------------

    def _laco(self) -> None:
        try:
            self._espia = subprocess.Popen(
                ["xprop", "-root", "-spy", "_NET_ACTIVE_WINDOW"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            )
        except OSError:
            return
        self._avaliar()
        for linha in self._espia.stdout:
            if self._parar.is_set():
                return
            self._avaliar(linha)

    def _avaliar(self, linha: str | None = None) -> None:
        identificador = self._ativa(linha)
        na_frente = False
        if identificador and identificador != self._nossa_janela:
            na_frente = self._em_tela_cheia(identificador)
        if na_frente != self._na_frente:
            self._na_frente = na_frente
            self.mudou.emit(na_frente)

    def _ativa(self, linha: str | None) -> int:
        if linha is None:
            try:
                linha = subprocess.run(["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                                       capture_output=True, text=True, timeout=2).stdout
            except (OSError, subprocess.SubprocessError):
                return 0
        try:
            return int(linha.strip().split()[-1], 16)
        except (ValueError, IndexError):
            return 0

    def _em_tela_cheia(self, identificador: int) -> bool:
        try:
            saida = subprocess.run(["xprop", "-id", hex(identificador), "_NET_WM_STATE"],
                                   capture_output=True, text=True, timeout=2).stdout
        except (OSError, subprocess.SubprocessError):
            return False
        return "_NET_WM_STATE_FULLSCREEN" in saida
