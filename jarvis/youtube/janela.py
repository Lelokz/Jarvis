"""A janela do Painel do Canal (PySide6 + QML, no estilo da NOVA, em roxo).

    python -m jarvis.youtube janela
    python -m jarvis.youtube retrato <arquivo.png> [inicio|videos] [id do vídeo]   (foto sem tela)
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QFontDatabase, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
import shiboken6

from jarvis.youtube import comentarios, conta, dados, editar, producao
from jarvis.interface import atomo_icone
from jarvis.interface.instancia import Instancia

AQUI = Path(__file__).resolve().parent
FONTES = AQUI.parent / "interface" / "fontes"


class Painel(QObject):
    mudou = Signal()
    aviso = Signal(str, bool)          # texto, deu certo
    trabalhando = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._dados: dict = {}
        self._ocupado = False
        self.recarregar()
        self._relogio = QTimer(self)
        self._relogio.timeout.connect(self.recarregar)
        self._relogio.start(60_000)     # o timer do systemd atualiza o banco a cada 30 min

    def _get(self) -> dict:
        return self._dados

    dados = Property("QVariantMap", _get, notify=mudou)

    @Slot()
    def recarregar(self) -> None:
        self._dados = dados.para_janela()
        self.mudou.emit()

    @Slot(str, result="QVariantList")
    def diasDoVideo(self, video: str) -> list:
        return dados.dias_do_video(video)

    def _em_fundo(self, fazer, ok: str) -> None:
        if self._ocupado:
            self.aviso.emit("Espera terminar o que está fazendo.", False)
            return
        self._ocupado = True
        self.trabalhando.emit(True)

        def rodar():
            try:
                fazer()
                msg, certo = ok, True
            except editar.Recusado as e:
                msg, certo = f"Não deu: {e}.", False
            except conta.SemConexao as e:
                msg, certo = f"Não deu: {e}.", False
            except Exception as e:  # noqa: BLE001 - erro do YouTube vira aviso na janela
                msg, certo = f"O YouTube recusou: {e}", False
            self._ocupado = False
            self.trabalhando.emit(False)
            self.recarregar()
            self.aviso.emit(msg, certo)
        threading.Thread(target=rodar, daemon=True).start()

    @Slot(str, str, str, str, str)
    def salvar(self, video: str, titulo: str, descricao: str, tags: str, visibilidade: str) -> None:
        lista = [t.strip() for t in tags.split(",")]
        self._em_fundo(lambda: editar.salvar_video(video, titulo, descricao, lista, visibilidade),
                       "Salvo no YouTube.")

    @Slot(str, str)
    def trocarThumb(self, video: str, url: str) -> None:
        caminho = QUrl(url).toLocalFile() or url
        self._em_fundo(lambda: editar.trocar_thumb(video, caminho), "Thumb trocada no YouTube.")

    @Slot()
    def sincronizar(self) -> None:
        self._em_fundo(dados.sincronizar, "Atualizado agora.")

    @Slot(str)
    def abrirLink(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    # -- etapa 3: agendar ------------------------------------------------------------

    @Slot(str, str, str)
    def agendar(self, video: str, data: str, hora: str) -> None:
        try:
            quando = editar.quando_de(data, hora)
        except editar.Recusado as e:
            self.aviso.emit(f"Não deu: {e}.", False)
            return
        self._em_fundo(lambda: editar.agendar(video, quando), f"Agendado pra {quando:%d/%m às %H:%M}.")

    @Slot(str, str)
    def reagendarNoDia(self, video: str, dia_iso: str) -> None:
        """O arrastar do calendário: mesmo horário, outro dia."""
        import datetime as dt
        atual = next((v for v in self._dados.get("videos", []) if v["id"] == video), None)
        if not atual or not atual.get("agendado"):
            return
        antes = dt.datetime.fromisoformat(atual["agendado"].replace("Z", "+00:00")).astimezone()
        dia = dt.date.fromisoformat(dia_iso)
        self.agendar(video, f"{dia:%d/%m/%Y}", f"{antes:%H:%M}")

    @Slot(str)
    def desagendar(self, video: str) -> None:
        self._em_fundo(lambda: editar.desagendar(video), "Tirado do agendamento (continua privado).")

    # -- etapa 4: comentários --------------------------------------------------------------

    @Slot(str, str)
    def responder(self, comentario: str, texto: str) -> None:
        self._em_fundo(lambda: comentarios.responder(comentario, texto), "Resposta publicada.")

    @Slot(str)
    def marcarLido(self, comentario: str) -> None:
        comentarios.marcar_lido([comentario])
        self.recarregar()

    @Slot()
    def marcarTodosLidos(self) -> None:
        comentarios.marcar_lido(None)
        self.recarregar()

    # -- etapa 3: produção (só no PC, na hora) -----------------------------------------

    def _no_pc(self, fazer, ok: str = "") -> None:
        try:
            fazer()
            if ok:
                self.aviso.emit(ok, True)
        except ValueError as e:
            self.aviso.emit(f"Não deu: {e}.", False)
        self.recarregar()

    @Slot("QVariantMap", result=int)
    def criarCard(self, campos: dict) -> int:
        novo = [0]
        self._no_pc(lambda: novo.__setitem__(0, producao.criar(dict(campos))))
        return novo[0]

    @Slot(int, "QVariantMap")
    def salvarCard(self, card: int, campos: dict) -> None:
        self._no_pc(lambda: producao.atualizar(card, dict(campos)), "Card salvo.")

    @Slot(int, str)
    def moverCard(self, card: int, coluna: str) -> None:
        self._no_pc(lambda: producao.mover(card, coluna))

    @Slot(int)
    def apagarCard(self, card: int) -> None:
        self._no_pc(lambda: producao.apagar(card), "Card apagado.")

    @Slot(str, result=str)
    def caminhoDe(self, url: str) -> str:
        return QUrl(url).toLocalFile() or url

    @Slot(str)
    def abrirArquivo(self, caminho: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(caminho))


def abrir(retrato: str | None = None, aba: str = "inicio", ficha: str = "") -> int:
    """`retrato`: tira uma foto da janela depois de 3 s e sai (para conferir sem tela)."""
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Painel do Canal")
    app.setDesktopFileName("painel-do-canal")
    app.setWindowIcon(QIcon.fromTheme("jarvis-atomo"))

    instancia = Instancia(nome="jarvis-painel-canal")
    if retrato is None and not instancia.tomar():
        return 0   # já estava aberta: ela vem para a frente

    for fonte in FONTES.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fonte))

    painel = Painel()
    engine = QQmlApplicationEngine()
    engine.addImageProvider("atomo", atomo_icone.ProvedorDoAtomo())
    engine.rootContext().setContextProperty("painel", painel)
    engine.rootContext().setContextProperty("abaInicial", aba)
    engine.rootContext().setContextProperty("fichaInicial", ficha)
    engine.rootContext().setContextProperty("rolarInicial", int(os.environ.get("PAINEL_ROLAR", "0")))
    engine.load(QUrl.fromLocalFile(str(AQUI / "Painel.qml")))
    if not engine.rootObjects():
        return 1
    raiz = engine.rootObjects()[0]
    janela = shiboken6.wrapInstance(shiboken6.getCppPointer(raiz)[0], QQuickWindow)

    def mostrar() -> None:
        janela.show()
        janela.raise_()
        janela.requestActivate()

    instancia.mostrarPedido.connect(mostrar)
    if retrato:
        def foto() -> None:
            try:
                janela.grabWindow().save(retrato)
            finally:
                app.quit()
        QTimer.singleShot(3000, foto)
    codigo = app.exec()
    instancia.soltar()
    return codigo
