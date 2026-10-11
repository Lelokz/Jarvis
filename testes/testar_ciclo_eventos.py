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
from jarvis import config, eventos  # noqa: E402
from jarvis.nucleo.nucleo import Resposta  # noqa: E402
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


class NucleoContador(ti.NucleoRoteirizado):
    def __init__(self):
        super().__init__()
        self.chamadas = []

    def processar(self, texto):
        self.chamadas.append(texto)
        return self.resposta


def montar(tmp, gravador, *, cfg=None, emissor=None, com_terminal=False):
    cfg = cfg or config.carregar(RAIZ / "config.toml")
    if emissor is None:
        emissor = eventos.Emissor()
        if com_terminal:
            t = assistente.Terminal(cfg.persona.nome.lower())
            emissor.assinar(t.receber, quer=t.quer, nome="terminal")
    emissor.assinar(gravador.receber, quer=gravador.quer, nome="gravador")
    vad, stt, nucleo = ti.VadRoteirizado(), ti.TranscritorRoteirizado(), NucleoContador()
    reg = Registrador(caminho_jsonl=tmp / f"s-{time.monotonic_ns()}.jsonl",
                      dir_audio=None, dir_audio_wake=None)
    ciclo = assistente.Ciclo(
        cfg, detector_vad=vad, detector_ww=ti.WakeWordParado(), transcritor=stt,
        voz=ti.VozMuda(), nucleo=nucleo, registrador=reg,
        portao=assistente._PortaoFalso(), dispositivo_saida=None, emissor=emissor,
    )
    return cfg, ciclo, vad, stt, nucleo, reg


def jsonl(reg):
    return [json.loads(l) for l in reg.caminho_jsonl.read_text().splitlines()]


def seno_bloco(rms_alvo: float) -> bytes:
    t = np.arange(512) / 16000.0
    amp = rms_alvo * math.sqrt(2) * 32767
    return (amp * np.sin(2 * math.pi * 500 * t)).astype(np.int16).tobytes()


def rodar(tmp: Path) -> None:
    print("-- E1. a sequência de estados numa conversa --")
    g = Gravador()
    cfg, ciclo, vad, stt, nucleo, _ = montar(tmp, g)
    with contextlib.redirect_stdout(io.StringIO()):
        ti.roteiro_base(ciclo, vad, stt, nucleo)
    esperado_estados = ["dormindo", "falando", "ouvindo",
                        "pensando", "falando", "ouvindo",
                        "pensando", "falando", "ouvindo",
                        "pensando", "ouvindo",
                        "dormindo"]
    checa("os estados saem na ordem de uma conversa real", g.estados() == esperado_estados,
          g.estados())
    esperado_tipos = [
        "estado", "acordou", "estado", "jarvis_disse", "janela", "estado",
        "estado", "voce_disse", "estado", "jarvis_disse", "tempos", "janela", "estado",
        "estado", "voce_disse", "estado", "jarvis_disse", "tempos", "janela", "estado",
        "estado", "nao_entendi", "janela", "estado",
        "quase_acerto",
        "estado", "dormiu",
    ]
    checa("e cada evento no seu lugar", g.tipos() == esperado_tipos, g.tipos())
    ditos = [e for e in g.eventos if e["ev"] == "jarvis_disse"]
    checa("a ação e a pergunta pendente atravessam",
          ditos[1]["acao"] == "abrir:loft" and ditos[2]["perguntando"] is True, ditos)
    checa("nenhum estado repetido em sequência",
          all(a != b for a, b in zip(g.estados(), g.estados()[1:])), g.estados())

    print("-- E2. escutando vem do VAD, sem piscar --")
    g = Gravador()
    cfg, ciclo, vad, stt, nucleo, _ = montar(tmp, g)
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
        nucleo.resposta = Resposta("Abri o Loft.", acao="abrir:loft")
        ciclo.passo(SILENCIO)          # o segmento fecha
    checa("fala → escutando; fala descartada → ouvindo; segmento → pensando direto",
          g.estados() == ["escutando", "ouvindo", "escutando", "pensando", "falando", "ouvindo"],
          g.estados())

    print("-- E3. texto digitado com o Jarvis dormindo --")
    g = Gravador()
    cfg, ciclo, vad, stt, nucleo, reg = montar(tmp, g, com_terminal=True)
    nucleo.resposta = Resposta("São cinco da tarde.")
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        ciclo.atender_texto("que horas são?")
    out = saida.getvalue()
    checa("acorda pelo texto", ciclo.estado is assistente.Estado.ACORDADO and ciclo.despertares == 1)
    checa("eventos: acordou, pensando, você disse, falando, resposta, janela, ouvindo",
          g.tipos() == ["estado", "acordou", "estado", "voce_disse", "estado",
                        "jarvis_disse", "janela", "estado"], g.tipos())
    checa("o acordar diz que foi pelo texto", g.eventos[1].get("por") == "texto", g.eventos[1])
    checa("a origem vai como texto", g.eventos[3].get("origem") == "texto", g.eventos[3])
    checa("SEM a saudação", not any(e["ev"] == "jarvis_disse" and e["texto"] == cfg.persona.saudacao
                                    for e in g.eventos) and cfg.persona.saudacao not in out, out)
    checa("o núcleo recebeu exatamente o texto", nucleo.chamadas == ["que horas são?"],
          nucleo.chamadas)
    checa("texto não conta como frase falada, nem gera linha de tempos",
          ciclo.frases == 0 and "stt " not in out, out)
    checa("o terminal mostra 'pelo texto digitado' e 'você (texto)'",
          "pelo texto digitado" in out and 'você (texto): "que horas são?"' in out, out)
    linhas = jsonl(reg)
    estados_log = [l.get("estado") for l in linhas if l.get("tipo") == "estado"]
    checa("o log registra: acordou pelo texto → texto digitado → decisão, nesta ordem",
          estados_log[:3] == ["acordou", "texto_digitado", "decisao"]
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
        cfg, ciclo, vad, stt, nucleo, _ = montar(tmp, g)
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
        cfg, ciclo, vad, stt, nucleo, _ = montar(tmp, g, com_terminal=True)
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
            _, ciclo, vad, stt, nucleo, _ = montar(tmp, g, cfg=cfg, emissor=emissor)

        cli = Cliente(caminho, quem="teste")
        cli.conectar()
        cli._sock.settimeout(3)
        fluxo = cli.eventos()
        sessao, estado0 = next(fluxo), next(fluxo)
        checa("o cliente recebe a sessão com o log desta sessão",
              sessao.get("ev") == "sessao" and sessao.get("log") == str(reg.caminho_jsonl), sessao)
        checa("e o estado atual, dormindo", estado0 == {"ev": "estado", "estado": "dormindo"},
              estado0)

        nucleo.resposta = Resposta("Abri o Loft.", acao="abrir:loft")
        cli.enviar_texto("abre o loft")
        fim = time.monotonic() + 3
        while ponte._pedidos.qsize() == 0 and time.monotonic() < fim:
            time.sleep(0.01)

        def uma_volta():  # o mesmo trecho do laço do conversar()
            if ponte is not None and not ciclo.vad.falando:
                texto = ponte.proximo_texto()
                if texto is not None:
                    ciclo.atender_texto(texto)

        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            vad.falando = True
            for _ in range(20):
                uma_volta()
            checa("com você falando, o texto ESPERA na fila",
                  nucleo.chamadas == [] and ponte._pedidos.qsize() == 1,
                  (nucleo.chamadas, ponte._pedidos.qsize()))
            vad.falando = False
            uma_volta()
        checa("com a fala terminada, é atendido", nucleo.chamadas == ["abre o loft"],
              nucleo.chamadas)
        chegou = [next(fluxo) for _ in range(5)]
        checa("o cliente vê: pensando, você disse, falando, resposta com ação, ouvindo",
              [e["ev"] for e in chegou] == ["estado", "voce_disse", "estado", "jarvis_disse", "estado"]
              and [e.get("estado") for e in chegou if e["ev"] == "estado"]
                  == ["pensando", "falando", "ouvindo"]
              and chegou[1] == {"ev": "voce_disse", "texto": "abre o loft", "origem": "texto"}
              and chegou[3].get("acao") == "abrir:loft", chegou)
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
            _, ciclo, vad, stt, nucleo, _ = montar(tmp, g, emissor=emissor)
            ti.roteiro_base(ciclo, vad, stt, nucleo)
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


    print("-- E10. bloquear a tela: a FALA vem antes da trava --")
    ordem = []

    class VozQueAnota(ti.VozMuda):
        """Anota quando a fala termina.

        O `tts.falar` consome o gerador até o fim; o que vem depois do `yield`
        roda exatamente quando a síntese acaba, dentro do laço dele. É o
        instante que o teste precisa comparar com o da trava.
        """

        def sintetizar(self, texto):
            ordem.append("fala começou")
            if False:  # noqa: SIM223  — mantém isto como gerador
                yield
            ordem.append("fala terminou")

    g = Gravador()
    cfg = config.carregar(RAIZ / "config.toml")
    emissor = eventos.Emissor()
    emissor.assinar(g.receber, quer=g.quer, nome="gravador")
    reg = Registrador(caminho_jsonl=tmp / "tela.jsonl", dir_audio=None,
                      dir_audio_wake=None)
    nucleo = NucleoContador()
    # O núcleo de verdade devolve um `depois` que trancaria a tela. Aqui ele é
    # trocado por um que só anota: NENHUM teste automático trava tela de
    # ninguém.
    nucleo.resposta = Resposta("Bloqueando.", acao="bloquear_tela",
                               depois=lambda: ordem.append("travou"))
    ciclo = assistente.Ciclo(
        cfg, detector_vad=ti.VadRoteirizado(), detector_ww=ti.WakeWordParado(),
        transcritor=ti.TranscritorRoteirizado(), voz=VozQueAnota(), nucleo=nucleo,
        registrador=reg, portao=assistente._PortaoFalso(), dispositivo_saida=None,
        emissor=emissor,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        ciclo.atender_texto("bloqueia o pc")
    checa("a trava acontece DEPOIS de a fala terminar",
          ordem == ["fala começou", "fala terminou", "travou"], ordem)
    checa("o núcleo recebeu o comando", nucleo.chamadas == ["bloqueia o pc"],
          nucleo.chamadas)
    linhas = jsonl(reg)
    depois_no_log = [l for l in linhas if l.get("estado") == "depois_da_fala"]
    checa("e o que rodou depois da fala foi registrado",
          len(depois_no_log) == 1 and depois_no_log[0].get("acao") == "bloquear_tela",
          depois_no_log)

    print("-- E11. sem `depois`, nada muda no caminho de sempre --")
    ordem.clear()
    nucleo.resposta = Resposta("Abri o Loft.", acao="abrir:loft")
    with contextlib.redirect_stdout(io.StringIO()):
        ciclo.atender_texto("abre o loft")
    checa("resposta comum não dispara nada depois da fala",
          ordem == ["fala começou", "fala terminou"], ordem)
    checa("e não registra linha de 'depois'",
          len([l for l in jsonl(reg) if l.get("estado") == "depois_da_fala"]) == 1,
          "registrou a mais")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-ciclo-"))
    try:
        rodar(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n  {ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
