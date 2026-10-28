"""A janela do instalador da NOVA (as 8 telas do protótipo aprovado em 26/10/2026,
mais as Conexões). Roda pelo `instalar-nova.sh`, com o Python e o PySide6 que o
`uv` traz, antes de a NOVA existir no PC.

    uv run --python 3.12 --with pyside6-essentials python -m nova_instalador
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QFontDatabase, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine

from nova_instalador import checar, passos
from nova_instalador.checar import SEM_JANELA, WINDOWS

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

    # -- tela 5: a conta do Claude -----------------------------------------------
    # {"logado": bool, "email", "plano", "url": o endereço do login, "erro"}
    claude = Signal("QVariant")

    def _claude_bin(self) -> str:
        return str(passos.CLAUDE)

    def _status_claude(self) -> dict:
        try:
            r = subprocess.run([self._claude_bin(), "auth", "status", "--json"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=20, **SEM_JANELA)
            d = json.loads(r.stdout or "{}")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return {"logado": False}
        return {"logado": bool(d.get("loggedIn")), "email": d.get("email") or "",
                "plano": (d.get("subscriptionType") or "").capitalize()}

    @Slot()
    def claudeConferir(self) -> None:
        threading.Thread(target=lambda: self.claude.emit(self._status_claude()), daemon=True).start()

    @Slot()
    def claudeEntrar(self) -> None:
        """`claude auth login`: pega o endereço que ele mostra (a janela abre no navegador)
        e fica esperando o código; confere a conta de 3 em 3 s até entrar."""
        if getattr(self, "_login", None) is not None and self._login.poll() is None:
            if getattr(self, "_url_login", ""):
                self.claude.emit({"logado": False, "url": self._url_login})
            return
        self._url_login = ""
        try:
            self._login = subprocess.Popen([self._claude_bin(), "auth", "login"], stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           env=dict(os.environ, BROWSER="true"), **SEM_JANELA)
        except OSError as erro:
            self.claude.emit({"logado": False, "erro": f"O Claude Code não abriu: {erro}"})
            return

        def ler() -> None:
            texto = b""
            while True:
                pedaco = os.read(self._login.stdout.fileno(), 4096)
                if not pedaco:
                    break
                texto += pedaco
                achou = re.search(rb"https://\S+", texto)
                if achou and not self._url_login:
                    self._url_login = achou.group(0).decode()
                    self.claude.emit({"logado": False, "url": self._url_login})

        def conferir() -> None:
            while self._login.poll() is None or not self._url_login:
                time.sleep(3)
                s = self._status_claude()
                if s["logado"]:
                    self.claude.emit(s)
                    self._login.kill()
                    return
                if self._login.poll() is not None:
                    break
            self.claude.emit(self._status_claude())

        threading.Thread(target=ler, daemon=True).start()
        threading.Thread(target=conferir, daemon=True).start()

    @Slot(str)
    def claudeCodigo(self, codigo: str) -> None:
        if getattr(self, "_login", None) is not None and self._login.poll() is None:
            self._login.stdin.write(codigo.strip().encode() + b"\n")
            self._login.stdin.flush()

    # -- tela 6: o microfone (o teste roda na NOVA instalada) -------------------
    microfone = Signal("QVariant")

    def _app(self) -> Path:
        return Path(self._escolhas.get("pasta") or self._pasta_padrao()).expanduser() / "app"

    def _python(self) -> str:
        return str(passos.python_do(self._app() / ".venv"))

    @Slot(result="QVariant")
    def entradas(self) -> list:
        if WINDOWS:   # a lista de microfones vem do som do Linux; no Windows o teste usa o padrão
            return []
        try:
            fontes = json.loads(subprocess.run(["pactl", "-f", "json", "list", "sources"], capture_output=True,
                                               text=True, timeout=5).stdout or "[]")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return []
        return [{"id": f["name"], "nome": f.get("description") or f["name"]} for f in fontes
                if not f.get("name", "").endswith(".monitor")]

    @Slot(str)
    def microfoneTestar(self, entrada: str) -> None:
        self.microfoneParar()
        app = self._app()
        cmd = [self._python(), "-m", "jarvis.teste_microfone"] + (["--entrada", entrada] if entrada else [])
        try:
            self._mic = subprocess.Popen(cmd, cwd=app, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL, text=True, encoding="utf-8", **SEM_JANELA)
        except OSError as erro:
            self.microfone.emit({"erro": str(erro)})
            return

        def ler(p=self._mic) -> None:
            for linha in p.stdout:
                try:
                    self.microfone.emit(json.loads(linha))
                except ValueError:
                    pass
        threading.Thread(target=ler, daemon=True).start()

    @Slot()
    def microfoneParar(self) -> None:
        p = getattr(self, "_mic", None)
        if p is not None and p.poll() is None:
            p.stdin.close()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()

    # -- tela 7: as conexões (o mesmo jarvis/conectar.py dos Ajustes) -----------
    conexao = Signal("QVariant")

    @Slot(str, str, str)
    def conectar(self, id_: str, acao: str, valor: str) -> None:
        p = getattr(self, "_conectar", None)
        if p is None or p.poll() is not None:
            app = self._app()
            self._conectar = p = subprocess.Popen([self._python(), "-m", "jarvis.conectar"], cwd=app,
                                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                  stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                                  **SEM_JANELA)

            def ler() -> None:
                for linha in p.stdout:
                    try:
                        self.conexao.emit(json.loads(linha))
                    except ValueError:
                        pass
            threading.Thread(target=ler, daemon=True).start()
        p.stdin.write(json.dumps({"id": id_, "acao": acao, "valor": valor}) + "\n")
        p.stdin.flush()

    # -- tela 8 --------------------------------------------------------------------
    @Slot()
    def abrirNova(self) -> None:
        """Liga a NOVA (o jarvis.sh, ou o jarvis/ligar.py no Windows, solto do instalador)."""
        if WINDOWS:
            cmd = [str(passos.python_do(self._app() / ".venv", sem_janela=True)), "-m", "jarvis.ligar"]
            solto = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS}
        else:
            cmd, solto = [str(self._app() / "jarvis.sh")], {"start_new_session": True}
        subprocess.Popen(cmd, cwd=self._app(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, **solto)

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
        """A pasta que o seletor devolve (file:///...) como caminho do sistema (no Windows,
        com \\), e uma pasta NOVA própria dentro dela, para não espalhar arquivos."""
        pasta = Path(QUrl(url).toLocalFile() or url)
        return str(pasta if pasta.name == "NOVA" else pasta / "NOVA")

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
