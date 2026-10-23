"""A ponte vista pelo Qt: evento do socket vira sinal.

Uma thread só conversa com o socket; ela emite os sinais, e o Qt entrega na
thread da interface (conexão automática = enfileirada quando as threads são
diferentes). O QML só enxerga sinais e um método para mandar texto.

A reconexão mora aqui, e não na janela: o Léo testou abrir a interface ANTES
do assistente existir, e é assim que ele vai usar — abrir a janela sem se
importar se o Jarvis já está rodando.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication

from jarvis.ponte import recebidos
from jarvis.ponte.cliente import Cliente

ESPERA_ENTRE_TENTATIVAS_S = 1.0
# Onde vão as imagens coladas com Ctrl+V antes de virarem anexo (o envio as
# copia para a pasta de recebidos). Limpa as de mais de um dia.
COLADOS = Path.home() / ".cache" / "jarvis" / "colados"
# Quantas falas anteriores a janela pede ao conectar. O assistente guarda até
# 200 e devolve o que tiver — este número é o que a conversa mostra ao abrir,
# inclusive quando a janela foi fechada e reaberta no meio do dia.
PEDIR_HISTORICO = 80


class PonteQt(QObject):
    estadoMudou = Signal(str)
    nivelMudou = Signal(float)
    voceDisse = Signal(str, str)           # texto, origem
    jarvisDisse = Signal(str, str, bool, list)   # texto, ação, perguntando, opções
    conexaoMudou = Signal(bool)
    sessaoRecebida = Signal(str, str)      # nome do Jarvis, caminho do log
    historicoRecebido = Signal(list)       # a conversa que já existia
    memoriaRecebida = Signal(list, list)   # fatos, conversas (mais nova primeiro)
    avisoMudou = Signal(str, float)        # "ok"|"limite"|"offline", volta_em (época, 0 = não sei)
    mostrar = Signal(str, str)             # título, texto em markdown (vai para a janela)
    atividade = Signal(str)                # o que o Claude está fazendo agora
    anexoFalhou = Signal(str)              # não deu para copiar/mandar o anexo
    memoriaTexto = Signal(str)             # o CLAUDE.md inteiro, em markdown
    # A janela grande (protocolo v3).
    cerebroMudou = Signal(str, str, str)   # modelo, esforço, persona
    conversaAtual = Signal(str, list, bool)  # id, falas, veio com as falas (troca)
    conversasRecebidas = Signal(list)      # a barra lateral
    conversaRecebida = Signal(str, list)   # uma conversa aberta só para ler
    erroRecebido = Signal(str)             # "espera ele terminar", pedido inválido
    usoMudou = Signal(float, float, float, float)  # 5 h (uso, volta_em), semana (uso, volta_em)
    escrevendo = Signal(int, str, bool, bool)      # bloco, pedaço, fim, descartar
    somMudou = Signal("QVariant")          # aparelhos de som: o evento "som" inteiro (Ajustes)
    ajustesMudou = Signal("QVariant")      # volume da voz e notificações da escola (Ajustes)

    def __init__(self, caminho: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._caminho = Path(caminho)
        self._cliente: Cliente | None = None
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._laco, name="ponte", daemon=True)

    def iniciar(self) -> None:
        self._thread.start()

    def encerrar(self) -> None:
        self._parar.set()
        cliente = self._cliente
        if cliente is not None:
            cliente.fechar()

    @Slot(str, result=bool)
    def enviarTexto(self, texto: str) -> bool:
        """Chamado pelo QML. Devolve False quando não há ninguém do outro lado."""
        cliente = self._cliente
        if cliente is None or not texto.strip():
            return False
        try:
            cliente.enviar_texto(texto)
        except OSError:
            return False
        return True

    @Slot(str, list, result=bool)
    def enviarComAnexos(self, texto: str, arquivos: list) -> bool:
        """O texto com os anexos do clipe (ou arrastados para a janela). Os
        arquivos são copiados para a pasta de recebidos (a única de onde a ponte
        aceita anexo) numa thread, para um vídeo grande não travar a janela."""
        cliente = self._cliente
        if cliente is None:
            return False
        caminhos = [Path(QUrl(str(a)).toLocalFile() or str(a)) for a in arquivos]

        def copiar_e_mandar() -> None:
            try:
                copiados = [str(recebidos.copiar(c)) for c in caminhos if c.is_file()]
                cliente.enviar_texto(texto.strip() or "Olha isso.", copiados)
            except OSError as e:
                self.anexoFalhou.emit(f"não consegui mandar o anexo ({e.strerror or e})")

        threading.Thread(target=copiar_e_mandar, name="anexos", daemon=True).start()
        return True

    @Slot(result=bool)
    def pedirMemoria(self) -> bool:
        cliente = self._cliente
        if cliente is None:
            return False
        try:
            cliente.pedir_memoria()
        except OSError:
            return False
        return True

    def _pedir(self, objeto: dict) -> bool:
        cliente = self._cliente
        if cliente is None:
            return False
        try:
            cliente.enviar(objeto)
        except OSError:
            return False
        return True

    @Slot(result=bool)
    def pedirConversas(self) -> bool:
        return self._pedir({"pedir": "conversas"})

    @Slot(str, result=bool)
    def abrirConversa(self, sessao: str) -> bool:
        return self._pedir({"pedir": "abrir", "id": sessao})

    @Slot(result=bool)
    def novaConversa(self) -> bool:
        return self._pedir({"pedir": "nova"})

    @Slot(str, result=bool)
    def continuarConversa(self, sessao: str) -> bool:
        return self._pedir({"pedir": "continuar", "id": sessao})

    @Slot(result=bool)
    def pedirSom(self) -> bool:
        return self._pedir({"pedir": "som"})

    @Slot(int, result=bool)
    def mudarVolumeVoz(self, volume: int) -> bool:
        return self._pedir({"pedir": "ajustes", "volume_voz": max(0, min(100, int(volume)))})

    @Slot(str, result=bool)
    def mudarCor(self, cor: str) -> bool:
        return self._pedir({"pedir": "ajustes", "cor": cor})

    @Slot(bool, result=bool)
    def mudarNotificarEscola(self, ligado: bool) -> bool:
        return self._pedir({"pedir": "ajustes", "notificar_escola": bool(ligado)})

    @Slot(str, str, result=bool)
    def escolherSom(self, tipo: str, aparelho: str) -> bool:
        """tipo = "saida" ou "entrada"; aparelho "" = o padrão do sistema."""
        return self._pedir({"pedir": "som", tipo: aparelho})

    @Slot(str, str, result=bool)
    def definirCerebro(self, modelo: str, esforco: str) -> bool:
        pedido = {"pedir": "cerebro"}
        if modelo:
            pedido["modelo"] = modelo
        if esforco:
            pedido["esforco"] = esforco
        return self._pedir(pedido)

    @Slot(str, str, result=bool)
    def renomearConversa(self, sessao: str, titulo: str) -> bool:
        return self._pedir({"pedir": "renomear", "id": sessao, "titulo": titulo})

    @Slot(str, result=bool)
    def apagarConversa(self, sessao: str) -> bool:
        return self._pedir({"pedir": "apagar", "id": sessao})

    @Slot(str, bool, result=bool)
    def fixarConversa(self, sessao: str, fixar: bool) -> bool:
        return self._pedir({"pedir": "fixar", "id": sessao, "fixar": fixar})

    @Slot(result=bool)
    def parar(self) -> bool:
        return self._pedir({"pedir": "parar"})

    @Slot(result=list)
    def colar(self) -> list:
        """O Ctrl+V da barra de escrever. Imagem na área de transferência (um
        print) vira arquivo; arquivos copiados no gerenciador vêm como estão.
        Devolve as URLs para anexar, ou [] quando é só texto (cola normal)."""
        dados = QGuiApplication.clipboard().mimeData()
        if dados is None:
            return []
        if dados.hasUrls():
            arquivos = [u.toString() for u in dados.urls() if u.isLocalFile() and Path(u.toLocalFile()).is_file()]
            if arquivos:
                return arquivos
        if dados.hasImage():
            imagem = QGuiApplication.clipboard().image()
            if imagem.isNull():
                return []
            COLADOS.mkdir(parents=True, exist_ok=True)
            agora = time.time()
            for velho in COLADOS.glob("*.png"):
                if agora - velho.stat().st_mtime > 86400:
                    velho.unlink(missing_ok=True)
            destino = COLADOS / time.strftime("colado-%Y%m%d-%H%M%S.png")
            if imagem.save(str(destino), "PNG"):
                return [QUrl.fromLocalFile(str(destino)).toString()]
        return []

    @Slot(str)
    def copiar(self, texto: str) -> None:
        QGuiApplication.clipboard().setText(texto)

    # ----------------------------------------------------------------------

    def _laco(self) -> None:
        while not self._parar.is_set():
            cliente = Cliente(self._caminho, quem="interface")
            try:
                cliente.conectar(historico=PEDIR_HISTORICO)
            except OSError:
                time.sleep(ESPERA_ENTRE_TENTATIVAS_S)
                continue
            self._cliente = cliente
            self.conexaoMudou.emit(True)
            try:
                for evento in cliente.eventos():
                    self._tratar(evento)
                    if self._parar.is_set():
                        break
            except (OSError, ValueError):
                pass
            self._cliente = None
            self.conexaoMudou.emit(False)
            cliente.fechar()

    def _tratar(self, ev: dict) -> None:
        tipo = ev.get("ev")
        if tipo == "estado":
            self.estadoMudou.emit(str(ev.get("estado", "")))
        elif tipo == "nivel":
            self.nivelMudou.emit(float(ev.get("v", 0.0)))
        elif tipo == "voce_disse":
            self.voceDisse.emit(str(ev.get("texto", "")), str(ev.get("origem", "")))
        elif tipo == "jarvis_disse":
            self.jarvisDisse.emit(str(ev.get("texto", "")), str(ev.get("acao") or ""),
                                  bool(ev.get("perguntando")), list(ev.get("opcoes") or []))
        elif tipo == "memoria":
            self.memoriaRecebida.emit(list(ev.get("fatos") or []),
                                      list(ev.get("conversas") or []))
            self.memoriaTexto.emit(str(ev.get("texto") or ""))
        elif tipo == "cerebro":
            self.cerebroMudou.emit(str(ev.get("modelo") or ""), str(ev.get("esforco") or ""),
                                   str(ev.get("persona") or "jarvis"))
        elif tipo == "conversa_atual":
            self.conversaAtual.emit(str(ev.get("id") or ""), list(ev.get("falas") or []),
                                    "falas" in ev)
        elif tipo == "conversas":
            self.conversasRecebidas.emit(list(ev.get("lista") or []))
        elif tipo == "som":
            self.somMudou.emit({k: v for k, v in ev.items() if k != "ev"})
        elif tipo == "ajustes":
            self.ajustesMudou.emit({k: v for k, v in ev.items() if k != "ev"})
        elif tipo == "conversa":
            self.conversaRecebida.emit(str(ev.get("id") or ""), list(ev.get("falas") or []))
        elif tipo == "erro":
            self.erroRecebido.emit(str(ev.get("motivo") or ""))
        elif tipo == "escrevendo":
            self.escrevendo.emit(int(ev.get("bloco") or 0), str(ev.get("delta") or ""),
                                 bool(ev.get("fim")), bool(ev.get("descartar")))
        elif tipo == "uso":
            c, s = ev.get("cinco_horas") or {}, ev.get("semana") or {}
            self.usoMudou.emit(float(c.get("uso") or -1), float(c.get("volta_em") or 0),
                               float(s.get("uso") or -1), float(s.get("volta_em") or 0))
        elif tipo == "aviso":
            self.avisoMudou.emit(str(ev.get("situacao") or "ok"), float(ev.get("volta_em") or 0))
        elif tipo == "mostrar":
            self.mostrar.emit(str(ev.get("titulo") or ""), str(ev.get("texto") or ""))
        elif tipo == "atividade":
            self.atividade.emit(str(ev.get("texto") or ""))
        elif tipo == "historico":
            self.historicoRecebido.emit(list(ev.get("falas") or []))
        elif tipo == "sessao":
            self.sessaoRecebida.emit(str(ev.get("nome", "")), str(ev.get("log", "")))
