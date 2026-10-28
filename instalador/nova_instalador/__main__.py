"""A janela do instalador da NOVA (as 8 telas do protótipo aprovado em 26/10/2026,
mais as Conexões). Roda pelo `instalar-nova.sh`, com o Python e o PySide6 que o
`uv` traz, antes de a NOVA existir no PC.

    uv run --python 3.12 --with pyside6-essentials python -m nova_instalador
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QFontDatabase, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine

from nova_instalador import checar, passos

AQUI = Path(__file__).resolve().parent
# O código da NOVA veio junto (o zip do GitHub): o tema, as fontes e o átomo da janela.
NOVA = AQUI.parent.parent
INTERFACE = NOVA / "jarvis" / "interface"
sys.path.insert(0, str(NOVA))


class Instalador(QObject):
    """O que a janela pede ao Python: conferir o PC, o espaço livre, as escolhas."""

    checou = Signal("QVariant")
    # A tela 4: {"passos": [{nome, tamanho, estado: esperando|agora|feito|erro}],
    #            "fracao": 0–1, "texto": "...", "fim": bool, "erro": "..."}
    progresso = Signal("QVariant")

    def __init__(self) -> None:
        super().__init__()
        self._escolhas: dict = {}
        self._nvidia = False
        self._rodando = False

    @Slot()
    def instalar(self) -> None:
        """Roda os passos que faltam (os feitos de outra vez são pulados)."""
        if self._rodando:
            return
        self._rodando = True
        e = self._escolhas
        ctx = passos.Contexto(pasta=Path(e.get("pasta") or self._pasta_padrao()).expanduser(), nvidia=self._nvidia,
                              dubladas=e.get("vozes") == "dubladas", nome=e.get("nome", ""),
                              persona=e.get("persona", "jarvis"), com_o_pc=bool(e.get("comOPc", True)),
                              atalho=bool(e.get("atalho", True)))
        threading.Thread(target=self._instalar, args=(ctx,), daemon=True).start()

    def _instalar(self, ctx: passos.Contexto) -> None:
        lista = passos.lista(ctx)
        total = sum(p.peso for p in lista)
        estados = ["feito" if passos.feito(ctx, p) else "esperando" for p in lista]

        def mandar(fracao: float, texto: str, **mais) -> None:
            self.progresso.emit({"passos": [{"nome": p.nome, "tamanho": p.tamanho, "estado": est}
                                            for p, est in zip(lista, estados)],
                                 "fracao": fracao, "texto": texto, **mais})

        for i, passo in enumerate(lista):
            if estados[i] == "feito":
                continue
            estados[i] = "agora"
            antes = sum(p.peso for p, est in zip(lista, estados) if est == "feito")

            def avisar(f: float, texto: str, passo=passo, antes=antes) -> None:
                dentro = passo.peso * (f if f >= 0 else 0.5)
                mandar((antes + dentro) / total, texto)

            avisar(0, passo.nome)
            try:
                passo.fazer(ctx, avisar)
            except Exception as erro:  # mostra na tela e deixa tentar de novo
                estados[i] = "erro"
                mandar(antes / total, f"{passo.nome}: parou aqui.", erro=str(erro)[-600:])
                self._rodando = False
                return
            passos.marcar(ctx, passo)
            estados[i] = "feito"
        mandar(1.0, "Pronto.", fim=True)
        self._rodando = False

    @Slot()
    def checar(self) -> None:
        # Em outra thread: o "internet" pode levar uns segundos.
        def conferir() -> None:
            dados = checar.tudo()
            self._nvidia = dados["nvidia"]
            self.checou.emit(dados)
        threading.Thread(target=conferir, daemon=True).start()

    @Slot(str, result=int)
    def discoLivre(self, pasta: str) -> int:
        return checar.disco(pasta)["livre_gb"]

    @Slot(str, result=str)
    def caminhoDe(self, url: str) -> str:
        """A pasta que o seletor devolve (file:///...) como caminho."""
        return QUrl(url).toLocalFile() or url

    @Slot("QVariant")
    def guardarEscolhas(self, escolhas) -> None:
        self._escolhas = dict(escolhas.toVariant() if hasattr(escolhas, "toVariant") else escolhas)

    def _pasta_padrao(self) -> str:
        return str(Path.home() / "NOVA")

    pastaPadrao = Property(str, _pasta_padrao, constant=True)

    def _nome_padrao(self) -> str:
        # O primeiro nome da conta do sistema, só como sugestão.
        try:
            import pwd
            nome = pwd.getpwuid(os.getuid()).pw_gecos.split(",")[0].split()[0]
        except (ImportError, KeyError, IndexError):
            nome = os.environ.get("USER", "") or os.environ.get("USERNAME", "")
        return nome[:30].capitalize()

    nomePadrao = Property(str, _nome_padrao, constant=True)


def main() -> int:
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Instalador da NOVA")
    app.setDesktopFileName("nova-instalador")
    app.setWindowIcon(QIcon(str(INTERFACE / "icone.png")))
    for fonte in (INTERFACE / "fontes").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fonte))
    instalador = Instalador()
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(INTERFACE / "qml"))
    # O ícone desenhado (o mesmo da janela, do menu e do app): image://atomo/<cor>.
    from jarvis.interface import atomo_icone
    engine.addImageProvider("atomo", atomo_icone.ProvedorDoAtomo())
    engine.rootContext().setContextProperty("instalador", instalador)
    engine.rootContext().setContextProperty("pastaQmlDaNova", QUrl.fromLocalFile(str(INTERFACE / "qml") + "/"))
    engine.load(QUrl.fromLocalFile(str(AQUI / "qml" / "Instalador.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
