#!/usr/bin/env python3
"""Jarvis — a interface (Etapa 6).

    .venv/bin/python interface.py
    .venv/bin/python interface.py --retratos rascunho/retratos   # um PNG por estado

**Processo separado do assistente, de propósito** (decisão do Léo): a interface
pode ser aberta, fechada e travar sem o Jarvis sentir, e pode subir antes dele
existir — ela fica esperando e conecta sozinha quando ele aparecer.

Aqui não há núcleo, microfone nem modelo. Só uma janela que mostra o que a
ponte conta e manda texto de volta.
"""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QFontDatabase, QGuiApplication, QSurfaceFormat
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from jarvis.interface import atomo_icone
from jarvis.interface.bandeja import Bandeja
from jarvis.interface.instancia import Instancia
from jarvis.interface.ponte_qt import PonteQt
from jarvis.interface.visibilidade import OlhoDeTelaCheia
from jarvis.ponte import protocolo

QML = Path(__file__).parent / "jarvis" / "interface" / "qml"

# Quadros: um a cada TRÊS sincronismos da tela (180 Hz ÷ 3 = 60 fps).
#
# Era 6 (30 fps), da janela pequena. Com ela, arrastar a janela ficava aos
# trancos ("parece 10 fps", 21/10/2026): a cada quadro o programa ficava preso
# esperando 6 sincronismos, e a sombra feita com efeito redesenhava tudo. A
# janela grande é opaca, sem esse efeito, e só anima o que aparece; parada,
# não desenha nada. O 3 é literal: trocar de monitor muda a taxa.
INTERVALO_DE_TROCA = 3
FONTES = Path(__file__).parent / "jarvis" / "interface" / "fontes"
ESTADOS = protocolo.ESTADOS


def _tirar_retratos(janela, destino: Path, app: QGuiApplication) -> None:
    """A própria janela se retrata, um estado por vez.

    O Qt captura a si mesmo: não depende de ferramenta de tela nem de acertar o
    tempo de um clique. Entre um estado e outro há espera, porque a transição é
    justamente o que precisa ser vista.
    """
    destino.mkdir(parents=True, exist_ok=True)
    janela.setProperty("conectado", True)
    janela.setProperty("demonstracao", True)

    # Os cinco estados, mais uma sequência do MESMO estado em instantes
    # diferentes: é a única forma de conferir num retrato o que só existe em
    # movimento — o anel passando atrás do núcleo.
    fila = [(f"{i}-{e}", e, 900) for i, e in enumerate(ESTADOS)]
    fila += [(f"5-giro-{n}", "ouvindo", 700) for n in range(1, 5)]
    fila += [("6-sem-conexao", "", 900)]

    def proximo():
        if not fila:
            QTimer.singleShot(200, app.quit)
            return
        nome, estado, espera = fila.pop(0)
        if nome == "6-sem-conexao":
            janela.setProperty("conectado", False)
        janela.setProperty("estado", estado)
        janela.setProperty("nivel", 0.75 if estado in ("escutando", "falando") else 0.0)
        QTimer.singleShot(espera, lambda: salvar(nome))

    def salvar(nome):
        # Pela tela, com o identificador da janela: o objeto raiz chega ao
        # Python como QWindow, que não tem `grabWindow`.
        imagem = app.primaryScreen().grabWindow(int(janela.winId()))
        caminho = destino / f"{nome}.png"
        imagem.save(str(caminho))
        print(f"  {caminho}", flush=True)
        proximo()

    QTimer.singleShot(600, proximo)


def _medir_quadros(janela, app: QGuiApplication) -> None:
    """O portão da Etapa 6 conferido na janela DE VERDADE, e não na prova de
    conceito: escondida, ela tem que desenhar zero quadro.
    """
    import os

    def cpu() -> float:
        with open("/proc/self/stat") as f:
            campos = f.read().rsplit(")", 1)[1].split()
        return (int(campos[11]) + int(campos[12])) / os.sysconf("SC_CLK_TCK")

    quadros = [0]
    janela.frameSwapped.connect(lambda: quadros.__setitem__(0, quadros[0] + 1))
    fases = [("visível", 6), ("minimizada", 9), ("restaurada", 5)]
    estado = {"i": 0, "s": 0, "amostras": [], "cpu0": cpu()}

    def tique():
        estado["s"] += 1
        n, quadros[0] = quadros[0], 0
        nome, duracao = fases[estado["i"]]
        if estado["s"] > 2:  # os dois primeiros segundos são transição
            estado["amostras"].append(n)
        if estado["s"] >= duracao:
            amostras = estado["amostras"] or [0]
            gasto = cpu() - estado["cpu0"]
            print(f"  {nome:12} {sum(amostras) / len(amostras):5.1f} fps  ·  "
                  f"CPU {100 * gasto / duracao:5.1f}% de um núcleo", flush=True)
            estado.update(i=estado["i"] + 1, s=0, amostras=[], cpu0=cpu())
            if estado["i"] >= len(fases):
                app.quit()
                return
            if fases[estado["i"]][0] == "minimizada":
                janela.showMinimized()
            else:
                janela.showNormal()

    relogio = QTimer(app)
    relogio.timeout.connect(tique)
    relogio.start(1000)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Jarvis — interface (Etapa 6).")
    p.add_argument("--socket", default="", help="padrão: $XDG_RUNTIME_DIR/jarvis.sock")
    p.add_argument("--retratos", type=Path, default=None,
                   help="salva um PNG de cada estado nesta pasta e sai")
    p.add_argument("--medir-quadros", action="store_true",
                   help="diagnóstico: conta quadros com a janela visível e minimizada")
    p.add_argument("--dizer", default="",
                   help="diagnóstico: manda este texto assim que conectar e retrata a conversa")
    p.add_argument("--na-bandeja", action="store_true",
                   help="sobe com a janela escondida, só o ícone na bandeja (ligar com o PC)")
    p.add_argument("--retrato-da-conversa", type=Path, default=None,
                   help="onde salvar o retrato do --dizer")
    args = p.parse_args(argv)

    # QApplication, e não QGuiApplication: o QSystemTrayIcon mora no QtWidgets.
    # Custa 5,8 MB de memória residente (65,7 -> 71,5 MB, medido isolado), e é
    # o preço do ícone no painel.
    app = QApplication(sys.argv)
    app.setApplicationName("Jarvis")
    # Esconder a janela na bandeja não pode encerrar o programa.
    app.setQuitOnLastWindowClosed(False)
    # "Desligar Jarvis" manda SIGTERM. Sem isto a interface morria na hora,
    # sem passar pelo `finally` lá embaixo, e o `xprop -spy` do vigia de tela
    # cheia ficava órfão a cada desligar. O relógio de 300 ms existe só para o
    # Python ganhar a vez de rodar o tratador: com o Qt no laço dele, o sinal
    # ficaria esperando até o próximo evento.
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    _acorda_python = QTimer(app)
    _acorda_python.timeout.connect(lambda: None)
    _acorda_python.start(300)

    modo_normal = not (args.retratos or args.medir_quadros or args.dizer)

    # Uma interface só. Antes de abrir janela: a segunda tentativa não deve
    # sequer piscar uma janela nova, e sim trazer a que já existe.
    instancia = Instancia()
    if modo_normal and not instancia.tomar():
        print("  o Jarvis já estava aberto — trouxe a janela para a frente")
        return 0

    # Sem pedir nada, a janela sem moldura desenhava à taxa cheia da tela —
    # três vezes o necessário, e trabalho jogado fora com o jogo do lado.
    formato = QSurfaceFormat.defaultFormat()
    formato.setSwapInterval(INTERVALO_DE_TROCA)
    QSurfaceFormat.setDefaultFormat(formato)
    if args.medir_quadros:
        hz = app.primaryScreen().refreshRate() if app.primaryScreen() else 0.0
        print(f"  tela {hz:.0f} Hz · intervalo {INTERVALO_DE_TROCA} · "
              f"alvo {hz / INTERVALO_DE_TROCA:.0f} fps", flush=True)

    # A fonte da janela (Inter, licença OFL) vem com o projeto.
    for fonte in FONTES.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fonte))

    ponte = PonteQt(protocolo.caminho_socket(args.socket))
    olho = OlhoDeTelaCheia()

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML))
    engine.rootContext().setContextProperty("ponte", ponte)
    engine.addImageProvider("atomo", atomo_icone.ProvedorDoAtomo())
    # Ligando com o PC, a janela não abre na cara: fica o ícone na bandeja.
    # Sem bandeja ela abre assim mesmo, senão não haveria porta de entrada.
    engine.rootContext().setContextProperty(
        "comecarNaBandeja", bool(args.na_bandeja and Bandeja.disponivel()))
    engine.load(QUrl.fromLocalFile(str(QML / "Janela.qml")))
    if not engine.rootObjects():
        print("a janela não carregou", file=sys.stderr)
        return 1
    janela = engine.rootObjects()[0]
    # A janela grande abre do tamanho da tela (pedido do Léo, 22/10/2026).
    if janela.isVisible():
        janela.showMaximized()

    # Os sinais da ponte o QML escuta sozinho (Connections no Janela.qml): o
    # chat precisa de dois deles que não viram propriedade, e repassar tudo
    # aqui seria uma costura a mais para divergir.
    #
    # A tela cheia continua vindo daqui, porque quem pergunta ao gerenciador de
    # janelas é o Python.
    olho.mudou.connect(lambda na_frente: janela.setProperty("jogoNaFrente", na_frente))
    olho.definirJanela(int(janela.winId()))

    # O ícone da janela (barra de tarefas) é o átomo na cor do estado, como o
    # da bandeja. A cor sai da JANELA, que é quem tem o Tema.
    def pintar_janela(*_):
        janela.setIcon(atomo_icone.icone(janela.property("corAtual"),
                                         bool(janela.property("conectado"))))

    ponte.estadoMudou.connect(pintar_janela)
    ponte.conexaoMudou.connect(pintar_janela)
    pintar_janela()

    def mostrar():
        janela.show()
        janela.raise_()
        janela.requestActivate()

    def alternar():
        if janela.isVisible():
            janela.hide()
        else:
            mostrar()

    instancia.mostrarPedido.connect(mostrar)

    bandeja = None
    if modo_normal and Bandeja.disponivel():
        bandeja = Bandeja(app)
        bandeja.mostrarPedido.connect(mostrar)
        bandeja.alternarPedido.connect(alternar)
        bandeja.encerrarPedido.connect(app.quit)
        # Só com ícone no painel a janela pode se esconder ao fechar: sem ele,
        # ela ficaria sem porta de volta.
        janela.setProperty("fecharEsconde", True)

        def pintar(*_):
            # A cor sai da JANELA, que é quem tem o Tema. Uma segunda paleta
            # aqui divergiria no dia em que alguém mexesse só numa delas.
            bandeja.definir(janela.property("corAtual"),
                            str(janela.property("estado") or ""),
                            bool(janela.property("conectado")))

        ponte.estadoMudou.connect(pintar)
        ponte.conexaoMudou.connect(pintar)
        pintar()
    elif modo_normal:
        print("  sem bandeja: o painel não tem applet de ícones de status.")
        print("  A janela continua funcionando; fechar encerra a interface.")

    if args.medir_quadros:
        # A ponte sobe junto: desconectada a esfera fica parada de propósito, e
        # a medição mediria o estado congelado em vez do animado.
        ponte.iniciar()
        _medir_quadros(janela, app)
    elif args.retratos is not None:
        _tirar_retratos(janela, args.retratos, app)
    elif args.dizer:
        # Diagnóstico da passada 3: prova o caminho inteiro do texto — QML →
        # ponte → socket → assistente → de volta ao chat — sem depender de
        # alguém digitando na janela.
        def quando_conectar(ligado):
            if not ligado:
                return
            QTimer.singleShot(300, lambda: ponte.enviarTexto(args.dizer))
            QTimer.singleShot(2000, retratar)

        def retratar():
            destino = args.retrato_da_conversa or Path("conversa.png")
            destino.parent.mkdir(parents=True, exist_ok=True)
            app.primaryScreen().grabWindow(int(janela.winId())).save(str(destino))
            print(f"  {destino}", flush=True)
            app.quit()

        ponte.conexaoMudou.connect(quando_conectar)
        ponte.iniciar()
        QTimer.singleShot(15000, app.quit)
    else:
        ponte.iniciar()
        olho.iniciar()

    try:
        return app.exec()
    finally:
        ponte.encerrar()
        olho.encerrar()
        instancia.soltar()
        if bandeja is not None:
            bandeja.esconder()


if __name__ == "__main__":
    raise SystemExit(main())
