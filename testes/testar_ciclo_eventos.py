"""O que é NOVO no Ciclo: estados, nível, texto digitado e a ligação inteira.

Complementa o terminal_identico.py, que prova que o terminal NÃO mudou. Este
prova o que passou a existir, com as mesmas peças falsas: sem microfone, sem
som, sem GPU e sem LLM. A ligação Ciclo → ponte → socket → cliente → Ciclo usa
o próprio `_abrir_ponte` do assistente e o mesmo trecho do laço do `conversar`.
"""
from __future__ import annotations

import contextlib
import dataclasses
import io
import json
import math
import os
import shutil
import socket
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[0]
sys.path.insert(0, str(RAIZ))

import assistente  # noqa: E402
import terminal_identico as ti  # noqa: E402
from jarvis import config, eventos, tts  # noqa: E402
from jarvis.ponte.servidor import Pedido  # noqa: E402
from jarvis.agente.agente import Saida  # noqa: E402
from jarvis.ponte.cliente import Cliente  # noqa: E402
from jarvis.registro import Registrador  # noqa: E402

ok = falhou = 0
SILENCIO = b"\x00" * 1024


def checa(nome, cond, detalhe=""):
    global ok, falhou
    if cond:
        ok += 1
        print(f"  PASSOU  {nome}", flush=True)
    else:
        falhou += 1
        print(f"  FALHOU  {nome}  {detalhe}", flush=True)


class Gravador:
    def __init__(self, quer_nivel=False):
        self.eventos = []
        self.quer_nivel = quer_nivel

    def quer(self, tipo):
        return self.quer_nivel or tipo != "nivel"

    def receber(self, ev):
        self.eventos.append(ev)

    def tipos(self):
        return [e["ev"] for e in self.eventos]

    def estados(self):
        return [e["estado"] for e in self.eventos if e["ev"] == "estado"]

    def limpar(self):
        self.eventos = []


def montar(tmp, gravador, *, cfg=None, emissor=None, com_terminal=False):
    cfg = cfg or config.carregar(RAIZ / "config.toml")
    if emissor is None:
        emissor = eventos.Emissor()
        if com_terminal:
            t = assistente.Terminal(cfg.persona.nome.lower())
            emissor.assinar(t.receber, quer=t.quer, nome="terminal")
    emissor.assinar(gravador.receber, quer=gravador.quer, nome="gravador")
    vad, stt, agente = ti.VadRoteirizado(), ti.TranscritorRoteirizado(), ti.AgenteRoteirizado()
    reg = Registrador(caminho_jsonl=tmp / f"s-{time.monotonic_ns()}.jsonl",
                      dir_audio=None, dir_audio_wake=None)
    ciclo = assistente.Ciclo(
        cfg, detector_vad=vad, detector_ww=ti.WakeWordParado(), transcritor=stt,
        voz=ti.VozMuda(), agente=agente, registrador=reg,
        portao=assistente._PortaoFalso(), dispositivo_saida=None, emissor=emissor,
    )
    # O conversar() anuncia o estado do Claude ("ok") na subida, antes de
    # qualquer pedido; aqui ninguém sobe, então fica marcado como anunciado.
    ciclo._ultimo_aviso = ("ok", None)
    return cfg, ciclo, vad, stt, agente, reg


def jsonl(reg):
    return [json.loads(l) for l in reg.caminho_jsonl.read_text().splitlines()]


def seno_bloco(rms_alvo: float) -> bytes:
    t = np.arange(512) / 16000.0
    amp = rms_alvo * math.sqrt(2) * 32767
    return (amp * np.sin(2 * math.pi * 500 * t)).astype(np.int16).tobytes()


def rodar(tmp: Path) -> None:
    print("-- E1. a sequência de estados numa conversa --")
    g = Gravador()
    cfg, ciclo, vad, stt, agente, _ = montar(tmp, g)
    with contextlib.redirect_stdout(io.StringIO()):
        ti.roteiro_base(ciclo, vad, stt, agente)
    esperado_estados = ["dormindo", "falando", "ouvindo",
                        "pensando", "falando", "ouvindo",
                        "pensando", "falando", "ouvindo",      # a pergunta falada
                        "pensando", "falando", "ouvindo",      # a resposta "pode"
                        "pensando", "ouvindo",
                        "dormindo"]
    checa("os estados saem na ordem de uma conversa real", g.estados() == esperado_estados,
          g.estados())
    esperado_tipos = [
        "estado", "acordou", "estado", "jarvis_disse", "janela", "estado",
        "estado", "voce_disse", "estado", "jarvis_disse", "tempos", "janela", "estado",
        "estado", "voce_disse", "estado", "jarvis_disse", "janela", "estado",
        "estado", "voce_disse", "estado", "jarvis_disse", "tempos", "janela", "estado",
        "estado", "nao_entendi", "janela", "estado",
        "quase_acerto",
        "estado", "dormiu",
    ]
    checa("e cada evento no seu lugar", g.tipos() == esperado_tipos, g.tipos())
    ditos = [e for e in g.eventos if e["ev"] == "jarvis_disse"]
    checa("a pergunta do Claude sai marcada como pergunta",
          ditos[2]["perguntando"] is True and ditos[3]["perguntando"] is False, ditos)
    checa("e a resposta falada a ela chega no Claude",
          agente.chamadas == ["abre o loft", "apaga a pasta lixo", "resposta: pode"],
          agente.chamadas)
    checa("nenhum estado repetido em sequência",
          all(a != b for a, b in zip(g.estados(), g.estados()[1:])), g.estados())

    print("-- E2. escutando vem do VAD, sem piscar --")
    g = Gravador()
    cfg, ciclo, vad, stt, agente, _ = montar(tmp, g)
    with contextlib.redirect_stdout(io.StringIO()):
        ciclo.acordar(0.9)
        g.limpar()
        vad.falando = True
        ciclo.passo(SILENCIO)
        ciclo.passo(SILENCIO)
        vad.falando = False
        ciclo.passo(SILENCIO)          # fala curta: o VAD descartou
        vad.falando = True
        ciclo.passo(SILENCIO)
        vad.falando = False
        vad.proximo = ti.segmento()
        stt.texto = "abre o loft"
        agente.resposta = Saida("fim", "Abri o Loft.")
        ciclo.passo(SILENCIO)          # o segmento fecha
        ciclo.atender_agente()
    checa("fala → escutando; fala descartada → ouvindo; segmento → pensando direto",
          g.estados() == ["escutando", "ouvindo", "escutando", "pensando", "falando", "ouvindo"],
          g.estados())

    print("-- E3. texto digitado com o Jarvis dormindo --")
    g = Gravador()
    cfg, ciclo, vad, stt, agente, reg = montar(tmp, g, com_terminal=True)
    agente.resposta = Saida("fim", "São cinco da tarde.")
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        ciclo.atender_texto("que horas são?")
        ciclo.atender_agente()
    out = saida.getvalue()
    checa("acorda pelo texto", ciclo.estado is assistente.Estado.ACORDADO and ciclo.despertares == 1)
    checa("eventos: acordou, pensando, você disse, falando, resposta, janela, ouvindo",
          g.tipos() == ["estado", "acordou", "estado", "voce_disse", "estado",
                        "jarvis_disse", "janela", "estado"], g.tipos())
    checa("o acordar diz que foi pelo texto", g.eventos[1].get("por") == "texto", g.eventos[1])
    checa("a origem vai como texto", g.eventos[3].get("origem") == "texto", g.eventos[3])
    checa("SEM a saudação", not any(e["ev"] == "jarvis_disse" and e["texto"] == cfg.persona.saudacao
                                    for e in g.eventos) and cfg.persona.saudacao not in out, out)
    checa("o núcleo recebeu exatamente o texto", agente.chamadas == ["que horas são?"],
          agente.chamadas)
    checa("texto não conta como frase falada, nem gera linha de tempos",
          ciclo.frases == 0 and "stt " not in out, out)
    checa("o terminal mostra 'pelo texto digitado' e 'você (texto)'",
          "pelo texto digitado" in out and 'você (texto): "que horas são?"' in out, out)
    linhas = jsonl(reg)
    estados_log = [l.get("estado") for l in linhas if l.get("tipo") == "estado"]
    checa("o log registra: acordou pelo texto → texto digitado → pedido, nesta ordem",
          estados_log[:3] == ["acordou", "texto_digitado", "pedido"]
          and linhas[0].get("por") == "texto" and linhas[1].get("texto") == "que horas são?",
          linhas[:3])

    print("-- E5. segundo texto com ele já acordado --")
    g.limpar()
    with contextlib.redirect_stdout(io.StringIO()):
        ciclo.atender_texto("e amanhã?")
    checa("não acorda de novo", "acordou" not in g.tipos() and ciclo.despertares == 1, g.tipos())

    print("-- E4. o nível do microfone --")
    contagem = [0]
    original = assistente._nivel

    def contando(bloco):
        contagem[0] += 1
        return original(bloco)

    assistente._nivel = contando
    try:
        g = Gravador(quer_nivel=True)
        cfg, ciclo, vad, stt, agente, _ = montar(tmp, g)
        with contextlib.redirect_stdout(io.StringIO()):
            ciclo.acordar(0.9)
            g.limpar()
            for _ in range(4):
                ciclo.passo(SILENCIO)
            silencio = [e["v"] for e in g.eventos if e["ev"] == "nivel"]
            g.limpar()
            for _ in range(2):
                ciclo.passo(seno_bloco(0.1))
            voz = [e["v"] for e in g.eventos if e["ev"] == "nivel"]
        checa("um nível a cada dois blocos", len(silencio) == 2 and len(voz) == 1, (silencio, voz))
        checa("silêncio digital dá 0", silencio == [0.0, 0.0], silencio)
        checa("-20 dBFS dá ~0,667", len(voz) == 1 and abs(voz[0] - 40 / 60) < 0.02, voz)

        contagem[0] = 0
        g = Gravador(quer_nivel=False)
        cfg, ciclo, vad, stt, agente, _ = montar(tmp, g, com_terminal=True)
        with contextlib.redirect_stdout(io.StringIO()):
            ciclo.acordar(0.9)
            for _ in range(20):
                ciclo.passo(seno_bloco(0.1))
        checa("sem ninguém querendo, o nível nem é calculado", contagem[0] == 0, contagem[0])
    finally:
        assistente._nivel = original

    print("-- E6. a ligação inteira: Ciclo → ponte → socket → cliente → Ciclo --")
    sockdir = Path(tempfile.mkdtemp(prefix="jarvis-e6-",
                                   dir=os.environ.get("XDG_RUNTIME_DIR") or None))
    try:
        caminho = sockdir / "j.sock"
        cfg = config.carregar(RAIZ / "config.toml")
        cfg = dataclasses.replace(cfg, ponte=config.Ponte(ligada=True, socket=str(caminho),
                                                          fila_max=256))
        reg = Registrador(caminho_jsonl=tmp / "e6.jsonl", dir_audio=None, dir_audio_wake=None)
        emissor = assistente._emissor_de_terminal(cfg)
        montagem = io.StringIO()
        with contextlib.redirect_stdout(montagem):
            ponte = assistente._abrir_ponte(cfg, reg, emissor)
        checa("_abrir_ponte sobe o servidor e anuncia no terminal",
              ponte is not None and str(caminho) in montagem.getvalue(), montagem.getvalue())
        g = Gravador()
        with contextlib.redirect_stdout(io.StringIO()):
            _, ciclo, vad, stt, agente, _ = montar(tmp, g, cfg=cfg, emissor=emissor)

        cli = Cliente(caminho, quem="teste")
        cli.conectar()
        cli._sock.settimeout(3)
        fluxo = cli.eventos()
        sessao, estado0 = next(fluxo), next(fluxo)
        checa("o cliente recebe a sessão com o log desta sessão",
              sessao.get("ev") == "sessao" and sessao.get("log") == str(reg.caminho_jsonl), sessao)
        checa("e o estado atual, dormindo", estado0 == {"ev": "estado", "estado": "dormindo"},
              estado0)

        agente.resposta = Saida("fim", "Abri o Loft.")
        cli.enviar_texto("abre o loft")
        fim = time.monotonic() + 3
        while ponte._pedidos.qsize() == 0 and time.monotonic() < fim:
            time.sleep(0.01)

        def uma_volta():  # o mesmo trecho do laço do conversar()
            if ponte is not None and not ciclo.vad.falando:
                texto = ponte.proximo_texto()
                if texto is not None:
                    ciclo.atender_texto(texto)
            if not ciclo.vad.falando:
                ciclo.atender_agente()

        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            vad.falando = True
            for _ in range(20):
                uma_volta()
            checa("com você falando, o texto ESPERA na fila",
                  agente.chamadas == [] and ponte._pedidos.qsize() == 1,
                  (agente.chamadas, ponte._pedidos.qsize()))
            vad.falando = False
            uma_volta()
        checa("com a fala terminada, é atendido", agente.chamadas == ["abre o loft"],
              agente.chamadas)
        chegou = [next(fluxo) for _ in range(5)]
        checa("o cliente vê: pensando, você disse, falando, resposta, ouvindo",
              [e["ev"] for e in chegou] == ["estado", "voce_disse", "estado", "jarvis_disse", "estado"]
              and [e.get("estado") for e in chegou if e["ev"] == "estado"]
                  == ["pensando", "falando", "ouvindo"]
              and chegou[1] == {"ev": "voce_disse", "texto": "abre o loft", "origem": "texto"}
              and chegou[3].get("texto") == "Abri o Loft.", chegou)
        checa("e o terminal do assistente mostrou o mesmo pedido",
              'você (texto): "abre o loft"' in saida.getvalue(), saida.getvalue())

        with contextlib.redirect_stdout(io.StringIO()):
            ciclo.passo(SILENCIO)
            ciclo.passo(SILENCIO)
        nivel = next(fluxo)
        checa("com cliente conectado, o nível atravessa o socket",
              nivel.get("ev") == "nivel" and nivel.get("v") == 0.0, nivel)

        cli.fechar()
        erro = None
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                ciclo.atender_texto("que horas são?")
                for _ in range(10):
                    ciclo.passo(SILENCIO)
        except Exception as e:  # noqa: BLE001
            erro = e
        checa("cliente sumiu no meio: o ciclo segue sem exceção", erro is None, erro)
        fim = time.monotonic() + 3
        while ponte.n_clientes and time.monotonic() < fim:
            time.sleep(0.01)
        checa("e a ponte percebe", ponte.n_clientes == 0, ponte.n_clientes)
        ponte.encerrar()
        checa("encerrar tira o socket", not os.path.lexists(caminho))
    finally:
        shutil.rmtree(sockdir, ignore_errors=True)

    print("-- E7. um assinante com defeito não derruba nada --")
    g = Gravador()
    emissor = eventos.Emissor()

    def quebrado(ev):
        raise ZeroDivisionError("defeito de propósito")

    emissor.assinar(quebrado, nome="quebrado")
    erros = io.StringIO()
    erro = None
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(erros):
            _, ciclo, vad, stt, agente, _ = montar(tmp, g, emissor=emissor)
            ti.roteiro_base(ciclo, vad, stt, agente)
    except Exception as e:  # noqa: BLE001
        erro = e
    checa("o ciclo inteiro roda com um assinante quebrando em todo evento", erro is None, erro)
    checa("os outros assinantes recebem tudo", len(g.eventos) == len(esperado_tipos),
          len(g.eventos))
    checa("e o defeito é avisado UMA vez, não a cada evento",
          erros.getvalue().count("falhou") == 1, erros.getvalue()[:300])

    print("-- E8. o Jarvis anterior morreu com kill -9 e deixou o socket para trás --")
    sockdir = Path(tempfile.mkdtemp(prefix="jarvis-e8-",
                                   dir=os.environ.get("XDG_RUNTIME_DIR") or None))
    try:
        caminho = sockdir / "j.sock"
        morto = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        morto.bind(str(caminho))
        morto.close()  # o arquivo fica e ninguém escuta
        cfg = dataclasses.replace(config.carregar(RAIZ / "config.toml"),
                                  ponte=config.Ponte(ligada=True, socket=str(caminho),
                                                     fila_max=256))
        reg = Registrador(caminho_jsonl=tmp / "e8.jsonl", dir_audio=None, dir_audio_wake=None)
        emissor = assistente._emissor_de_terminal(cfg)
        saida, erro, ponte = io.StringIO(), None, None
        try:
            with contextlib.redirect_stdout(saida):
                ponte = assistente._abrir_ponte(cfg, reg, emissor)
        except Exception as e:  # noqa: BLE001
            erro = e
        checa("o assistente sobe, sem exceção", erro is None, repr(erro))
        checa("e a ponte abre por cima do socket morto",
              ponte is not None and str(caminho) in saida.getvalue(), saida.getvalue())
        if ponte is not None:
            cli = Cliente(caminho, quem="teste")
            cli.conectar()
            cli._sock.settimeout(3)
            checa("e responde nele", next(cli.eventos()).get("ev") == "sessao")
            cli.fechar()
            ponte.encerrar()
    finally:
        shutil.rmtree(sockdir, ignore_errors=True)

    print("-- E9. uma ponte com defeito INESPERADO não impede o assistente de subir --")
    original = assistente.Servidor.iniciar

    def iniciar_quebrado(self):
        raise AttributeError("defeito de propósito")

    assistente.Servidor.iniciar = iniciar_quebrado
    try:
        cfg = dataclasses.replace(config.carregar(RAIZ / "config.toml"),
                                  ponte=config.Ponte(ligada=True, socket=str(tmp / "q.sock"),
                                                     fila_max=256))
        reg = Registrador(caminho_jsonl=tmp / "e9.jsonl", dir_audio=None, dir_audio_wake=None)
        emissor = assistente._emissor_de_terminal(cfg)
        saida, erro, ponte = io.StringIO(), None, "não chamou"
        try:
            with contextlib.redirect_stdout(saida):
                ponte = assistente._abrir_ponte(cfg, reg, emissor)
        except Exception as e:  # noqa: BLE001
            erro = e
        checa("_abrir_ponte devolve None em vez de explodir", erro is None and ponte is None,
              (repr(erro), ponte))
        checa("e avisa no terminal qual foi o defeito",
              "defeito ao abrir (AttributeError" in saida.getvalue(), saida.getvalue())
        checa("e a ponte quebrada não ficou assinando eventos", not emissor.quer("nivel"))
    finally:
        assistente.Servidor.iniciar = original


def rodar_celular(tmp: Path) -> None:
    """O celular é um corpo: o que ele pede é respondido LÁ, sem acordar o
    microfone do PC nem tocar na caixa de som."""
    from jarvis import tts
    from jarvis.ponte import protocolo
    from jarvis.ponte.servidor import Pedido

    class VozDeUmTrecho(tts.Voz):
        nome = "um trecho"

        def sintetizar(self, texto):
            yield tts.Trecho(pcm=b"\x01\x00" * 4000, taxa=40000, canais=1)

    class PortaoContado:
        fechou = 0

        def fechar_portao(self):
            PortaoContado.fechou += 1

        def abrir_portao(self):
            pass

    falas_no_pc = []
    original = tts.falar
    tts.falar = lambda voz, texto, **k: falas_no_pc.append(texto) or original(voz, texto, **k)
    try:
        print("-- E10. pedido do celular: a voz vai para ele, e o PC dorme --")
        g = Gravador()
        _, ciclo, _, stt, agente, _ = montar(tmp, g)
        ciclo.voz, ciclo.portao = VozDeUmTrecho(), PortaoContado()
        agente.resposta = Saida("fim", texto="São três da tarde.")
        ciclo.atender_pedido(Pedido("falar", "que horas são", cliente=7, voz=True))
        ciclo.atender_agente()
        disse = [e for e in g.eventos if e["ev"] == "voce_disse"]
        vozes = [e for e in g.eventos if e["ev"] == "voz"]
        checa("o pedido chega ao Claude marcado como do celular",
              agente.chamadas == ["que horas são"] and disse and disse[0]["origem"] == "celular",
              (agente.chamadas, disse))
        checa("a voz sai em eventos 'voz' para o cliente 7, com o fim",
              len(vozes) == 2 and all(v["para"] == 7 for v in vozes) and vozes[0]["taxa"] == 40000
              and vozes[-1].get("fim") is True, vozes)
        checa("o texto da resposta também vai (jarvis_disse)",
              any(e["ev"] == "jarvis_disse" and e["texto"] == "São três da tarde." for e in g.eventos))
        checa("e nada toca no PC, nem o portão fecha", falas_no_pc == [] and PortaoContado.fechou == 0,
              (falas_no_pc, PortaoContado.fechou))
        checa("o microfone do PC continua dormindo",
              ciclo.estado is assistente.Estado.DORMINDO and "acordou" not in g.tipos()
              and g.estados()[-1] == "dormindo", g.estados())

        print("-- E11. fala gravada no celular: transcrita, apagada, respondida lá --")
        g.limpar()
        pasta = protocolo.pasta_audio()
        pasta.mkdir(mode=0o700, exist_ok=True)
        arquivo = pasta / f"teste-{time.monotonic_ns()}.pcm"
        arquivo.write_bytes(b"\x00\x00" * 16000)
        stt.texto = "toca uma música"
        agente.resposta = Saida("fim", texto="Tocando.")
        ciclo.atender_pedido(Pedido("ouvir", str(arquivo), cliente=7, voz=True))
        ciclo.atender_agente()
        checa("o arquivo é apagado depois de lido", not arquivo.exists())
        checa("a transcrição vai ao Claude e a voz ao celular",
              agente.chamadas[-1] == "toca uma música"
              and any(e["ev"] == "voz" and e.get("pcm") for e in g.eventos), agente.chamadas)

        print("-- E13. anexo do celular vai para o Claude junto do pedido --")
        recebidos = []
        original_pedir = agente.pedir
        agente.pedir = lambda texto, origem="voz", contexto="", voz=None: (
            recebidos.append((texto, contexto)), original_pedir(texto, origem, contexto))
        agente.resposta = Saida("fim", texto="É uma praia.")
        ciclo.atender_pedido(Pedido("falar", "o que é isso?", cliente=7, voz=True,
                                    anexos=("/home/x/recebidos/foto.jpg",)))
        ciclo.atender_agente()
        checa("o caminho do anexo vai no contexto do pedido",
              recebidos and "/home/x/recebidos/foto.jpg" in recebidos[-1][1]
              and recebidos[-1][0] == "o que é isso?", recebidos)
        agente.pedir = original_pedir

        print("-- E14. celular no mudo: só o texto, a voz nem é gerada --")
        g.limpar()
        agente.resposta = Saida("fim", texto="Tudo certo.")
        ciclo.atender_pedido(Pedido("falar", "tudo bem?", cliente=7, voz=True, mudo=True))
        ciclo.atender_agente()
        checa("no mudo vai o texto e nenhum evento de voz",
              any(e["ev"] == "jarvis_disse" for e in g.eventos) and "voz" not in g.tipos(), g.tipos())

        print("-- E15. anexo pela janela do PC (sem voz própria) também vai ao Claude --")
        recebidos = []
        original_pedir = agente.pedir
        agente.pedir = lambda texto, origem="voz", contexto="", voz=None: (
            recebidos.append(contexto), original_pedir(texto, origem, contexto))
        agente.resposta = Saida("fim", texto="Vi.")
        ciclo.atender_pedido(Pedido("falar", "olha isso", cliente=1, voz=False,
                                    anexos=("/home/x/recebidos/print.png",)))
        ciclo.atender_agente()
        checa("o anexo da janela chega no contexto", recebidos and "print.png" in recebidos[-1], recebidos)
        agente.pedir = original_pedir
        ciclo.dormir("fim do E15")  # o E12 confere o acordar de novo

        print("-- E16. aviso de WhatsApp com a conversa no celular: sai no PC, não lá --")
        from jarvis.agente.avisos import Aviso

        class AvisosFalsos:
            def __init__(self):
                self.dados = Aviso(falar=["A Mãe mandou: compra pão."], mostrar=[], ouvir=False,
                                   contexto="")

            def checar(self):
                d, self.dados = self.dados, None
                return d

        g.limpar()
        antes = len(falas_no_pc)
        ciclo.avisos = AvisosFalsos()
        ciclo._corpo = 7  # a conversa estava no celular
        ciclo.anunciar_whatsapp()
        checa("o aviso toca no PC e nenhum evento de voz vai para o celular",
              len(falas_no_pc) == antes + 1 and "voz" not in g.tipos(), (falas_no_pc[antes:], g.tipos()))
        checa("e a conversa continua sendo do celular", ciclo._corpo == 7)
        ciclo.avisos = None

        print("-- E12. depois, falar no PC devolve a voz para a caixa de som --")
        g.limpar()
        ciclo.atender_pedido(Pedido("falar", "e agora?", cliente=1, voz=False))
        ciclo.atender_agente()
        checa("o texto da janela acorda o PC e fala nele",
              "acordou" in g.tipos() and "voz" not in g.tipos() and falas_no_pc, (g.tipos(), falas_no_pc))
    finally:
        tts.falar = original


def rodar_personas(tmp: Path) -> None:
    """As duas personas (25/10/2026): "hey Friday" troca voz, frases e a marca
    do pedido; "hey Jarvis" volta; a janela troca pelo pedido "cerebro"."""
    print("\nAS DUAS PERSONAS")

    class VozQueAnota(tts.Voz):
        def __init__(self, nome):
            self._nome, self.falas = nome, []

        @property
        def nome(self):
            return self._nome

        def sintetizar(self, texto):
            self.falas.append(texto)
            return iter(())

    class WakeWordComRotulo(ti.WakeWordParado):
        ultimo_rotulo = "hey_jarvis_v0.1"

    cfg = config.carregar(RAIZ / "config.toml")
    gravador = Gravador()
    emissor = eventos.Emissor()
    emissor.assinar(gravador.receber, quer=gravador.quer, nome="gravador")
    vj, vf, ww = VozQueAnota("jarvis"), VozQueAnota("friday"), WakeWordComRotulo()
    agente = ti.AgenteRoteirizado()
    agente.persona = "jarvis"
    reg = Registrador(caminho_jsonl=tmp / "personas.jsonl", dir_audio=None, dir_audio_wake=None)
    ciclo = assistente.Ciclo(
        cfg, detector_vad=ti.VadRoteirizado(), detector_ww=ww, transcritor=ti.TranscritorRoteirizado(),
        voz=vj, voz_friday=vf, agente=agente, registrador=reg,
        portao=assistente._PortaoFalso(), dispositivo_saida=None, emissor=emissor,
    )
    ciclo._ultimo_aviso = ("ok", None)
    ww.ultimo_rotulo = cfg.friday.modelo_wake
    ciclo.acordar(0.9)
    checa("'hey Friday' acorda a Friday", ciclo.persona == "friday" and agente.persona == "friday")
    checa("a saudação sai na voz dela, com a frase dela", vf.falas[-1:] == [cfg.persona_friday.saudacao],
          f"{vf.falas} / {vj.falas}")
    cerebro = [e for e in gravador.eventos if e["ev"] == "cerebro"]
    checa("a janela fica sabendo (persona e cor)", cerebro and cerebro[-1]["persona"] == "friday"
          and cerebro[-1]["cor_persona"] == cfg.friday.cor, str(cerebro[-1:]))
    ciclo.dormir("teste")
    ww.ultimo_rotulo = cfg.wakeword.modelo
    ciclo.acordar(0.9)
    checa("'hey Jarvis' volta para o JARVIS", ciclo.persona == "jarvis" and vj.falas[-1:] == [cfg.persona.saudacao],
          f"{vj.falas}")
    ciclo.atender_pedido(Pedido(cliente=1, tipo="cerebro", valor='{"persona": "friday"}'))
    checa("o seletor da janela troca para a Friday", ciclo.persona == "friday" and ciclo.voz is vf)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-ciclo-"))
    try:
        rodar(tmp)
        rodar_celular(tmp)
        rodar_personas(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n  {ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
