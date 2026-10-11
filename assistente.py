#!/usr/bin/env python3
"""Jarvis — o cliente de voz.

Dorme escutando só o wake word. Ao ouvir "hey Jarvis", cumprimenta, abre uma
janela de 30s e escuta. Sem fala, volta a dormir sozinho.

**Este arquivo é um cliente, não o Jarvis** (ESCOPO §4). Ele cuida de ouvir e
falar: microfone, wake word, VAD, Whisper, Piper e o ciclo de vida. Quem decide
o que fazer e executa é `jarvis/nucleo/`, do outro lado da linha — este laço
entrega texto e recebe texto, e não sabe o que é atalho, tabela ou LLM.

É essa divisão que vai permitir um cliente de celular depois sem reescrever
nada: só o transporte muda.

O `etapa0.py` continua existindo e intocado — é o banco de medição de latência
e o `--autoteste`, que é o primeiro diagnóstico quando algo aqui quebrar.
"""

from __future__ import annotations

import argparse
import dataclasses
import math
import sys
import time
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

import numpy as np

from jarvis import config, cronometro, eventos, microfone, tts, wakeword
from jarvis.cronometro import Tempos
from jarvis.nucleo.nucleo import ErroDoCerebro, Nucleo
from jarvis.ponte import protocolo
from jarvis.ponte.servidor import Servidor, ServidorOcupado
from jarvis.registro import Registrador
from jarvis.stt import ErroDeCuda, Transcritor
from jarvis.vad import DetectorDeFala

REGUA = "─" * 56


class Estado(Enum):
    DORMINDO = auto()
    ACORDADO = auto()


# ---------------------------------------------------------------------------
# apoio
# ---------------------------------------------------------------------------


def _vram() -> str:
    import subprocess

    try:
        saida = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        usada, total = saida.stdout.strip().splitlines()[0].split(",")
        return f"{int(usada) / 1024:.1f} GB / {int(total) / 1024:.1f} GB"
    except Exception:
        return "(nvidia-smi indisponível)"


def _partida(rotulo: str, detalhe: str, segundos: float | None = None) -> None:
    tempo = f"{segundos:>6.2f} s" if segundos is not None else ""
    print(f"  {rotulo:<16} {detalhe:<30}{tempo}")


def _linha(rotulo: str, detalhe: str = "") -> None:
    print(f"  {datetime.now():%H:%M:%S}   {rotulo:<18}{detalhe}")


class _PortaoFalso:
    """Substitui o microfone no --teste-ciclo, que não abre stream nenhum."""

    estouros = 0

    def fechar_portao(self) -> None: ...
    def abrir_portao(self) -> None: ...


class Terminal:
    """O terminal como UM assinante dos eventos do ciclo (Etapa 6, passada 2).

    Cada linha aqui é a mesma que o `Ciclo` imprimia direto até a Etapa 5.5, no
    mesmo instante e com o mesmo texto. A promessa da passada 2 é que o terminal
    fica idêntico — e ela foi conferida contra uma saída gravada antes da
    refatoração, linha a linha.
    """

    _TIPOS = frozenset({
        "acordou", "dormiu", "janela", "quase_acerto", "nao_entendi",
        "voce_disse", "jarvis_disse", "tempos",
    })

    def __init__(self, nome_do_jarvis: str) -> None:
        self.nome = nome_do_jarvis

    def quer(self, tipo: str) -> bool:
        return tipo in self._TIPOS

    def receber(self, ev: eventos.Evento) -> None:
        tipo = ev["ev"]
        if tipo == "acordou":
            if ev.get("por") == "texto":
                _linha("ACORDOU", "pelo texto digitado")
            else:
                _linha("ACORDOU", f"score {ev['score']:.2f}")
        elif tipo == "dormiu":
            _linha("dormiu", ev["motivo"])
        elif tipo == "janela":
            _linha(ev["rotulo"], f"{ev['janela_s']:g} s")
        elif tipo == "quase_acerto":
            _linha("quase-acerto", f"pico {ev['pico']:.2f}  (áudio gravado)")
        elif tipo == "nao_entendi":
            _linha("não entendi", "(nada transcrito — janela renovada)")
        elif tipo == "voce_disse":
            if ev.get("origem") == "texto":
                print(f'             você (texto): "{ev["texto"]}"')
            else:
                print(f'             você:   "{ev["texto"]}"')
        elif tipo == "jarvis_disse":
            print(f"             {self.nome}: \"{ev['texto']}\"")
        elif tipo == "tempos":
            print(
                f"             {'':<8}stt {ev['stt_s']:.2f}s · "
                f"núcleo {ev['nucleo_s']:.2f}s · "
                f"tts {ev['tts_s']:.2f}s · "
                f"latência {ev['latencia_s']:.2f}s"
            )


def _emissor_de_terminal(cfg: config.Config) -> eventos.Emissor:
    emissor = eventos.Emissor()
    terminal = Terminal(cfg.persona.nome.lower())
    emissor.assinar(terminal.receber, quer=terminal.quer, nome="terminal")
    return emissor


def _nivel(bloco: bytes) -> float:
    """O volume de um bloco do microfone, de 0 a 1, em escala de decibéis.

    Em dB e não linear porque é assim que o ouvido percebe volume: numa escala
    linear, a diferença entre falar baixo e falar normal quase não mexeria a
    esfera. -60 dBFS é o chão, 0 dBFS o teto.
    """
    amostras = np.frombuffer(bloco, dtype=np.int16).astype(np.float32) / 32768.0
    if amostras.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(amostras * amostras)))
    if rms < 1e-6:
        return 0.0
    return round(min(1.0, max(0.0, (20.0 * math.log10(rms) + 60.0) / 60.0)), 3)


# ---------------------------------------------------------------------------
# o ciclo
# ---------------------------------------------------------------------------


class Ciclo:
    """Máquina de estados dormindo ↔ acordado.

    Recebe blocos de áudio um a um por `passo()`. Quem alimenta é o laço
    principal (microfone) ou o --teste-ciclo (áudio sintético) — a máquina não
    sabe a diferença, e é isso que torna o teste possível sem voz.
    """

    def __init__(
        self,
        cfg: config.Config,
        *,
        detector_vad: DetectorDeFala,
        detector_ww: wakeword.Detector,
        transcritor: Transcritor,
        voz: tts.Voz,
        nucleo: Nucleo,
        registrador: Registrador,
        portao,
        dispositivo_saida: int | None,
        emissor: eventos.Emissor | None = None,
    ) -> None:
        self.cfg = cfg
        self.nucleo = nucleo
        self.vad = detector_vad
        self.ww = detector_ww
        self.transcritor = transcritor
        self.voz = voz
        self.registrador = registrador
        self.portao = portao
        self.dispositivo_saida = dispositivo_saida
        # Quem escuta o que o ciclo faz. Sem emissor dado, é só o terminal: o
        # --teste-ciclo e qualquer uso antigo continuam imprimindo igual.
        self.emissor = emissor or _emissor_de_terminal(cfg)

        self.estado = Estado.DORMINDO
        self.prazo = 0.0
        self.guarda_s = cfg.audio.guarda_pos_fala_ms / 1000

        self.despertares = 0
        self.frases = 0
        self.acoes = 0
        self.vazias = 0
        self.eventos_wake = 0
        self.resumo = cronometro.Resumo()
        self._desde = time.monotonic()
        self.tempo_dormindo = 0.0
        self.tempo_acordado = 0.0

        # O estado que os clientes MOSTRAM. Mais fino que `self.estado`, que só
        # conhece dormindo e acordado: acordado se divide em ouvindo, escutando,
        # pensando e falando, porque é isso que o Léo quer saber olhando, sem
        # precisar ouvir (Etapa 6).
        self._visivel: str | None = None
        self._blocos_acordado = 0
        self._mudar_estado("dormindo")

    # -- transições --------------------------------------------------------

    def _contabilizar(self) -> None:
        agora = time.monotonic()
        if self.estado is Estado.DORMINDO:
            self.tempo_dormindo += agora - self._desde
        else:
            self.tempo_acordado += agora - self._desde
        self._desde = agora

    def acordar(self, score: float) -> None:
        self._contabilizar()
        self.despertares += 1
        self.emissor.emitir("acordou", score=score)
        self.registrador.registrar_estado("acordou", score=round(score, 5))

        # O evento do disparo ainda está juntando o pós-roll, e daqui a uma
        # linha ninguém mais alimenta o detector do wake word. Fechar agora é
        # o que salva o .wav do despertar — sem isto ele morreria no
        # reiniciar(), e seria justamente o áudio mais importante do log.
        pendente = self.ww.fechar_pendente()
        if pendente is not None:
            self._registrar_evento(pendente)

        # Manda o LLM se carregar agora, em segundo plano. A saudação leva
        # 1-2s e você ainda vai levar mais alguns falando o comando — tempo
        # que já está sendo gasto e que esconde a recarga de ~7,5s.
        self.nucleo.aquecer()

        self._falar(self.cfg.persona.saudacao)
        self.estado = Estado.ACORDADO
        self._renovar("janela aberta")

    def dormir(self, motivo: str) -> None:
        self._contabilizar()
        self.estado = Estado.DORMINDO
        # Obrigatório: o openWakeWord guarda 2-3s de features. Sem zerar, o
        # "hey Jarvis" que causou este despertar ainda está no buffer dele e
        # pontua de novo assim que voltarmos a dormir — acordando sozinho, em
        # laço, sem o microfone ter captado nada.
        self.ww.reiniciar()
        self.vad.reiniciar()
        # Confirmação ou busca pendente não atravessam o sono: senão a
        # primeira fala do próximo despertar viraria filtro de uma busca velha.
        self.nucleo.reiniciar_conversa()
        self._mudar_estado("dormindo")
        self.emissor.emitir("dormiu", motivo=motivo)
        self.registrador.registrar_estado("dormiu", motivo=motivo)

    def _renovar(self, rotulo: str) -> None:
        self.prazo = time.monotonic() + self.cfg.ciclo.janela_s
        self.emissor.emitir("janela", rotulo=rotulo, janela_s=self.cfg.ciclo.janela_s)
        self.registrador.registrar_estado(rotulo, janela_s=self.cfg.ciclo.janela_s)
        self._mudar_estado("ouvindo")

    def _falar(
        self, texto: str, *, acao: str | None = None, perguntando: bool = False
    ) -> tts.TemposDaFala:
        """Fala com o portão anti-eco fechado.

        Sem isto o microfone pega a própria voz do Jarvis: o VAD dispara e ele
        se responde, e — pior neste etapa — o wake word pode se ouvir e acordar
        de novo em laço.
        """
        self._mudar_estado("falando")
        self.emissor.emitir(
            "jarvis_disse", texto=texto, acao=acao, perguntando=perguntando
        )
        self.portao.fechar_portao()
        try:
            return tts.falar(self.voz, texto, dispositivo=self.dispositivo_saida)
        finally:
            time.sleep(self.guarda_s)
            self.portao.abrir_portao()
            self.ww.reiniciar()
            self.vad.reiniciar()

    # -- laço --------------------------------------------------------------

    def passo(self, bloco: bytes) -> None:
        if self.estado is Estado.DORMINDO:
            self._dormindo(bloco)
        else:
            self._acordado(bloco)

    def _dormindo(self, bloco: bytes) -> None:
        disparou, evento = self.ww.processar(bloco)
        if evento is not None:
            self._registrar_evento(evento)
        if disparou:
            self.acordar(self.ww.ultimo_score)

    def _registrar_evento(self, evento: wakeword.Evento) -> None:
        self.eventos_wake += 1
        self.registrador.registrar_wake(
            pico=evento.pico,
            disparou=evento.disparou,
            pcm=evento.pcm,
            taxa=self.cfg.audio.taxa_amostragem,
            frames=evento.frames,
        )
        if not evento.disparou:
            # Quase-acerto: não acordou, mas chegou perto. É o dado que explica
            # um acordar indevido meses depois.
            self.emissor.emitir("quase_acerto", pico=evento.pico)

    def _acordado(self, bloco: bytes) -> None:
        segmento = self.vad.processar(bloco)
        self._talvez_nivel(bloco)

        if segmento is None:
            # O que os clientes mostram enquanto você fala é o VAD, não uma
            # suposição: `falando` é atualizado a cada bloco de 32 ms.
            if self.vad.falando:
                self._mudar_estado("escutando")
            elif self._visivel == "escutando":
                # A fala era curta demais e o VAD a descartou.
                self._mudar_estado("ouvindo")
            # Nunca dormir no meio de uma frase: se a janela vencer com o VAD
            # em fala, esperar ele fechar o segmento.
            if time.monotonic() >= self.prazo and not self.vad.falando:
                self.dormir(f"{self.cfg.ciclo.janela_s:g} s sem fala")
            return

        self._mudar_estado("pensando")
        transcricao = self.transcritor.transcrever(segmento.audio)

        if not transcricao.texto:
            # O VAD ouviu, o Whisper não achou palavra. Fica calado (não ecoar
            # alucinação é regra desde a Etapa 0), mas a janela reinicia: você
            # falou, e deixar o relógio correr puniria você por uma falha dele.
            self.vazias += 1
            self.emissor.emitir("nao_entendi")
            self.registrador.registrar_descarte(
                "transcricao vazia",
                {"duracao_s": round(segmento.duracao_total_s, 3)},
            )
            self._renovar("janela reiniciada")
            return

        self._responder(
            transcricao.texto, origem="voz", segmento=segmento, transcricao=transcricao
        )

    def _responder(
        self,
        texto: str,
        *,
        origem: str,
        segmento=None,
        transcricao=None,
    ) -> None:
        """Entrega o texto ao núcleo, fala a resposta e renova a janela.

        Um caminho só para voz e para texto digitado. Duplicar isto para o
        texto seria escrever uma segunda chance de divergir — e a primeira
        divergência seria justamente num log ou numa confirmação.
        """
        self._mudar_estado("pensando")
        self.emissor.emitir("voce_disse", texto=texto, origem=origem)

        # Aqui o cliente entrega o texto e recebe texto. Tudo o que decide e
        # executa está do outro lado da linha do ESCOPO §4 — este laço não
        # sabe o que é atalho, tabela ou LLM.
        inicio_nucleo = time.monotonic()
        resposta = self.nucleo.processar(texto)
        nucleo_s = time.monotonic() - inicio_nucleo
        if resposta.acao:
            self.acoes += 1
        # O diagnóstico do núcleo vai inteiro para o log. Sem ele, investigar
        # por que um comando falhou obrigava a reproduzir a sessão fala por
        # fala — foi o que aconteceu depois do primeiro teste com voz real.
        self.registrador.registrar_estado(
            "decisao",
            resposta=resposta.texto,
            acao=resposta.acao,
            perguntando=resposta.perguntando,
            **resposta.diagnostico,
        )
        fala = self._falar(
            resposta.texto, acao=resposta.acao, perguntando=resposta.perguntando
        )

        # O que o núcleo pediu para rodar DEPOIS da fala (Etapa 6.6). Este laço
        # não sabe o que é — só sabe que agora pode, porque o `_falar` só
        # retorna quando o áudio acabou de tocar. É o que faz "bloqueia o PC"
        # falar antes de a tela apagar, sem ninguém adivinhar a duração da fala.
        if resposta.depois is not None:
            feito = resposta.depois()
            self.registrador.registrar_estado(
                "depois_da_fala",
                acao=resposta.acao,
                ok=getattr(feito, "ok", None),
                mensagem=getattr(feito, "mensagem", ""),
                detalhe=getattr(feito, "detalhe", None),
            )

        # Tempos e .wav só existem para o que foi FALADO: texto digitado não
        # tem segmento, nem Whisper, nem espera de silêncio para medir.
        if segmento is not None and transcricao is not None:
            tempos = Tempos(
                duracao_segmento_s=segmento.duracao_total_s,
                espera_silencio_s=segmento.espera_silencio_s,
                stt_s=transcricao.segundos,
                nucleo_s=nucleo_s,
                tts_primeiro_s=fala.primeiro_audio_s,
                tts_total_s=fala.sintese_total_s,
                reproducao_s=fala.reproducao_s,
            )
            self.frases += 1
            self.resumo.adicionar(tempos)
            self.registrador.registrar_frase(
                segmento=segmento,
                texto=transcricao.texto,
                tempos=tempos,
                idioma=transcricao.idioma,
                probabilidade_idioma=transcricao.probabilidade_idioma,
            )
            self.emissor.emitir(
                "tempos",
                stt_s=transcricao.segundos,
                nucleo_s=nucleo_s,
                tts_s=fala.primeiro_audio_s,
                latencia_s=tempos.latencia_percebida_s,
            )
        # A janela reinicia quando ELE termina de responder, não quando você
        # termina de falar.
        self._renovar("janela reiniciada")

    # -- texto digitado (Etapa 6) ------------------------------------------

    def atender_texto(self, texto: str) -> None:
        """Um pedido digitado num cliente, atendido como se tivesse sido falado.

        **Roda na thread de áudio, nunca na do socket.** O Nucleo guarda estado
        de conversa — confirmação pendente, busca aberta — e duas threads nele
        fariam uma confirmação falada e uma digitada se atropelarem.

        Decisão do Léo: digitar acorda mesmo dormindo, e a resposta sai na voz.
        Sem a saudação: ela existe para confirmar que o wake word pegou, e aqui
        o próprio texto já é o comando.
        """
        if self.estado is Estado.DORMINDO:
            self._acordar_por_texto()
        self.registrador.registrar_estado("texto_digitado", texto=texto)
        self._responder(texto, origem="texto")

    def _acordar_por_texto(self) -> None:
        self._contabilizar()
        self.despertares += 1
        self.emissor.emitir("acordou", por="texto")
        self.registrador.registrar_estado("acordou", por="texto")
        pendente = self.ww.fechar_pendente()
        if pendente is not None:
            self._registrar_evento(pendente)
        self.vad.reiniciar()
        self.estado = Estado.ACORDADO

    # -- o que os clientes veem --------------------------------------------

    def _mudar_estado(self, nome: str) -> None:
        """Emite o estado visível só quando ele MUDA."""
        if nome != self._visivel:
            self._visivel = nome
            self.emissor.emitir("estado", estado=nome)

    def _talvez_nivel(self, bloco: bytes) -> None:
        """Um nível a cada dois blocos (~15 por segundo), e só se alguém quer.

        Um a cada dois porque o bloco do Silero é de 32 ms: todo bloco seriam
        31 mensagens por segundo, mais do que uma animação precisa.
        """
        self._blocos_acordado += 1
        if self._blocos_acordado % 2 == 0 and self.emissor.quer("nivel"):
            self.emissor.emitir("nivel", v=_nivel(bloco))

    # -- fim ---------------------------------------------------------------

    def formatar_resumo(self) -> str:
        self._contabilizar()
        total = self.tempo_dormindo + self.tempo_acordado or 1.0
        por_despertar = self.frases / self.despertares if self.despertares else 0.0
        linhas = [
            "",
            REGUA,
            "  RESUMO DA SESSÃO",
            REGUA,
            f"  despertares{self.despertares:>43}",
            f"  frases dentro da janela{self.frases:>31}",
            f"  ações executadas{self.acoes:>38}",
            f"  frases por despertar{por_despertar:>34.1f}",
            f"  transcrições vazias{self.vazias:>35}",
            f"  eventos de wake word gravados{self.eventos_wake:>25}",
            REGUA,
            f"  tempo dormindo{self.tempo_dormindo / 60:>36.1f} min"
            f"  ({self.tempo_dormindo / total:.0%})",
            f"  tempo acordado{self.tempo_acordado / 60:>36.1f} min"
            f"  ({self.tempo_acordado / total:.0%})",
            REGUA,
        ]
        return "\n".join(linhas) + "\n" + self.resumo.formatar(
            descartados=self.vad.descartados_curtos, vazias=self.vazias
        )


# ---------------------------------------------------------------------------
# montagem
# ---------------------------------------------------------------------------


def _montar(cfg: config.Config):
    """Carrega as quatro peças e reporta o custo de partida de cada uma."""
    inicio = time.monotonic()
    detector_vad = DetectorDeFala(cfg.vad, cfg.audio.taxa_amostragem)
    _partida("VAD", "Silero via pysilero-vad", time.monotonic() - inicio)

    detector_ww = wakeword.Detector(
        cfg.wakeword,
        cfg.dir_modelos_wake,
        amostras_por_bloco=detector_vad.amostras_por_bloco,
        taxa=cfg.audio.taxa_amostragem,
    )
    _partida("wake word", detector_ww.descricao, detector_ww.segundos_de_carga)

    transcritor = Transcritor(cfg.stt)
    _partida("Whisper", transcritor.descricao, transcritor.segundos_de_carga)
    _partida("aquecimento", "(1ª inferência, descartada)", transcritor.aquecer())

    voz = tts.criar_voz(cfg.tts, cfg.dir_vozes)
    _partida("Piper", voz.nome, voz.segundos_de_carga)

    inicio = time.monotonic()
    nucleo = Nucleo(cfg)
    _partida("núcleo", nucleo.descricao, time.monotonic() - inicio)

    # O LLM entra na VRAM AQUI, e não no primeiro comando.
    #
    # O "pronto" mentia por omissão: o wake word e o Whisper ficavam
    # residentes, mas o qwen3:8b — o único que só o comando usa — continuava no
    # disco. O primeiro comando pagava a leitura de 5,23 GB, medida em 14,8s
    # com cache frio contra 1,2s em cache. Do wake word até a resposta dava
    # 18,7s de média, contra 6,2s do segundo comando em diante.
    #
    # Isto não cria espera nova: move os 15 segundos para dentro de uma espera
    # que já existe. O Léo espera o "pronto" antes de falar; agora o "pronto"
    # é verdade.
    #
    # A mensagem antes é de propósito. Ver o terminal parado 15 segundos sem
    # explicação é diferente de ver o que está acontecendo.
    aviso = "  LLM              carregando na VRAM (5 GB, pode levar ~15 s)..."
    # No terminal o aviso é reescrito no lugar; num log ele fica como linha
    # própria. O "\r" não apaga nada quando a saída não é um terminal, e sem
    # esta checagem o log sai com os dois textos grudados na mesma linha.
    terminal = sys.stdout.isatty()
    print(aviso, end="" if terminal else "\n", flush=True)
    segundos = nucleo.carregar()
    if terminal:
        print("\r" + " " * len(aviso) + "\r", end="")
    _partida("LLM", f"{cfg.llm.modelo} na VRAM", segundos)

    # O cliente lê os nomes do núcleo e entrega ao Whisper como vocabulário.
    # A direção é permitida pela linha da §4: cliente conhece o núcleo, o
    # núcleo não conhece o cliente. Medido: sem vocabulário 4/15 dos nomes
    # sobrevivem à fala rápida, com vocabulário 9/15, sem custo de latência.
    nomes = [a.nome for a in nucleo.tabela.atalhos]
    transcritor.usar_vocabulario(nomes)
    _partida(
        "vocabulário",
        f"{len(nomes)} nomes do atalhos.toml"
        if transcritor.vocabulario
        else "desligado no config.toml",
    )

    # O Whisper fica residente: a Etapa 0 mediu ~6,4s de carga mais ~1,9s de
    # aquecimento, e pagar isso a cada acordar mataria a sensação de resposta.
    # Só o ciclo lógico dorme.
    _partida("VRAM em uso", f"{_vram()}   (residente)")
    _partida("janela", f"{cfg.ciclo.janela_s:g} s")

    return detector_vad, detector_ww, transcritor, voz, nucleo


def _abrir_ponte(
    cfg: config.Config, registrador: Registrador, emissor: eventos.Emissor
) -> Servidor | None:
    """Abre o canal para os outros clientes (Etapa 6).

    **Nunca impede o assistente de subir.** Desligada, ocupada por outro Jarvis
    ou com erro, ele avisa e segue — a voz funciona igual sem cliente nenhum.
    """
    if not cfg.ponte.ligada:
        _partida("ponte", "desligada no config.toml")
        return None
    caminho = protocolo.caminho_socket(cfg.ponte.socket)
    servidor = Servidor(
        caminho,
        fila_max=cfg.ponte.fila_max,
        sessao={
            "v": protocolo.VERSAO,
            "nome": cfg.persona.nome,
            "log": str(registrador.caminho_jsonl),
        },
    )
    try:
        servidor.iniciar()
    except ServidorOcupado:
        servidor.encerrar()
        _partida("ponte", "OCUPADA — outro Jarvis já responde nela; seguindo sem")
        return None
    except OSError as e:
        servidor.encerrar()
        _partida("ponte", f"não abriu ({e}); seguindo sem")
        return None
    except Exception as e:
        # Defeito da própria ponte, e não do sistema. Pego aqui de propósito:
        # o teste da passada 2 achou um — com o socket deixado por um Jarvis
        # morto, a ponte caía em AttributeError, e esta função, que só
        # esperava OSError, teria derrubado o assistente inteiro na subida
        # seguinte a um travamento. É a promessa da docstring virando código.
        servidor.encerrar()
        _partida("ponte", f"defeito ao abrir ({e.__class__.__name__}: {e}); seguindo sem")
        return None
    emissor.assinar(servidor.receber, quer=servidor.quer, nome="ponte")
    _partida("ponte", str(caminho))
    return servidor


# ---------------------------------------------------------------------------
# modos
# ---------------------------------------------------------------------------


def teste_ciclo(cfg: config.Config) -> int:
    """Exercita a máquina de estados sem microfone.

    Alimenta a mesma `Ciclo.passo()` do laço real com silêncio sintético e
    força um despertar. Prova as transições, os `reiniciar()` e o portão sem
    depender da voz do Léo — que é o que eu não consigo produzir.
    """
    print("\nTESTE DO CICLO (sem microfone)\n" + REGUA)
    janela_curta = 3.0
    cfg = dataclasses.replace(cfg, ciclo=config.Ciclo(janela_s=janela_curta))

    try:
        detector_vad, detector_ww, transcritor, voz, nucleo = _montar(cfg)
    except (ErroDeCuda, ErroDoCerebro, wakeword.ModeloAusente, FileNotFoundError) as e:
        print(f"\n{e}\n", file=sys.stderr)
        return 1

    ciclo = Ciclo(
        cfg,
        detector_vad=detector_vad,
        detector_ww=detector_ww,
        transcritor=transcritor,
        voz=voz,
        nucleo=nucleo,
        registrador=Registrador.criar(cfg, prefixo="teste-ciclo"),
        portao=_PortaoFalso(),
        dispositivo_saida=None,
    )

    silencio = b"\x00" * (detector_vad.amostras_por_bloco * 2)
    print(REGUA)

    _linha("estado inicial", ciclo.estado.name)
    if ciclo.estado is not Estado.DORMINDO:
        print("  FALHOU: deveria começar dormindo.")
        return 1

    # Silêncio enquanto dorme: não pode acordar sozinho.
    for _ in range(30):
        ciclo.passo(silencio)
    if ciclo.estado is not Estado.DORMINDO:
        print("  FALHOU: acordou com silêncio.")
        return 1
    _linha("1s de silêncio", "continuou dormindo — ok")

    # Força o despertar: fala a saudação de verdade e abre a janela.
    ciclo.acordar(0.99)
    if ciclo.estado is not Estado.ACORDADO:
        print("  FALHOU: não acordou.")
        return 1

    # Silêncio dentro da janela até ela vencer.
    limite = time.monotonic() + janela_curta + 3
    while ciclo.estado is Estado.ACORDADO and time.monotonic() < limite:
        ciclo.passo(silencio)

    if ciclo.estado is not Estado.DORMINDO:
        print(f"  FALHOU: não voltou a dormir depois de {janela_curta:g}s.")
        return 1

    # E depois de dormir, continua dormindo (o reset do wake word funcionou).
    for _ in range(30):
        ciclo.passo(silencio)
    if ciclo.estado is not Estado.DORMINDO:
        print("  FALHOU: acordou sozinho depois de dormir (buffer não zerou).")
        return 1
    _linha("depois de dormir", "não acordou sozinho — ok")

    print(REGUA)
    print("  PASSOU — dorme, acorda, escuta a janela e volta a dormir.\n")
    return 0


def conversar(cfg: config.Config) -> int:
    print(f"\n{cfg.persona.nome} — cliente de voz")

    try:
        indice_entrada = microfone.resolver(cfg.audio.dispositivo_entrada, entrada=True)
        indice_saida = microfone.resolver(cfg.audio.dispositivo_saida, entrada=False)
    except ValueError as e:
        print(f"\n{e}\n", file=sys.stderr)
        return 1
    _partida("microfone", microfone.nome_do_dispositivo(indice_entrada, entrada=True))

    try:
        detector_vad, detector_ww, transcritor, voz, nucleo = _montar(cfg)
    except ErroDeCuda as e:
        print(f"\nCUDA não subiu:\n{e}\n", file=sys.stderr)
        return 1
    except (ErroDoCerebro, wakeword.ModeloAusente, FileNotFoundError) as e:
        print(f"\n{e}\n", file=sys.stderr)
        return 1

    registrador = Registrador.criar(cfg, prefixo="jarvis")
    emissor = _emissor_de_terminal(cfg)
    ponte = _abrir_ponte(cfg, registrador, emissor)

    mic: microfone.Microfone | None = None
    ciclo: Ciclo | None = None
    try:
        with microfone.Microfone(
            taxa=cfg.audio.taxa_amostragem,
            amostras_por_bloco=detector_vad.amostras_por_bloco,
            dispositivo=indice_entrada,
        ) as mic:
            _checar_nivel(mic)
            print(f"\n  log              {registrador.caminho_jsonl}")
            print(
                f"  áudio wake       {registrador.dir_audio_wake}/"
                f"  (teto {cfg.log.max_audios_wake})"
            )
            ciclo = Ciclo(
                cfg,
                detector_vad=detector_vad,
                detector_ww=detector_ww,
                transcritor=transcritor,
                voz=voz,
                nucleo=nucleo,
                registrador=registrador,
                portao=mic,
                dispositivo_saida=indice_saida,
                emissor=emissor,
            )
            print(REGUA)
            _linha("dormindo", 'diga "hey Jarvis"  (ctrl+c encerra)')

            while True:
                bloco = mic.ler_bloco()
                if bloco is not None:
                    ciclo.passo(bloco)
                # Texto digitado num cliente. Atendido AQUI, na thread de áudio,
                # e só com o VAD fora de fala: quem digita enquanto fala espera
                # a frase acabar, em vez de ter a própria voz cortada.
                if ponte is not None and not ciclo.vad.falando:
                    texto = ponte.proximo_texto()
                    if texto is not None:
                        ciclo.atender_texto(texto)

    except KeyboardInterrupt:
        print()
    finally:
        if ciclo is not None:
            pendente = detector_ww.fechar_pendente()
            if pendente is not None:
                registrador.registrar_wake(
                    pico=pendente.pico,
                    disparou=pendente.disparou,
                    pcm=pendente.pcm,
                    taxa=cfg.audio.taxa_amostragem,
                    frames=pendente.frames,
                )
            print(ciclo.formatar_resumo())
        if mic is not None and mic.estouros:
            print(f"  blocos perdidos pelo PortAudio: {mic.estouros}")
        print(f"  registro em {registrador.caminho_jsonl}\n")
        if ponte is not None:
            ponte.encerrar()
    return 0


def _checar_nivel(mic: microfone.Microfone, segundos: float = 1.0) -> None:
    """Mede o microfone antes de começar.

    O Fifine tem mute no próprio corpo, invisível para o PipeWire — ele reporta
    `Mudo: não` enquanto o hardware entrega silêncio digital. Sem esta
    checagem, o Jarvis ficaria "dormindo" para sempre e pareceria bug de
    software.
    """
    picos = []
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        bloco = mic.ler_bloco(timeout=0.3)
        if bloco is not None:
            picos.append(np.abs(np.frombuffer(bloco, dtype=np.int16)).max())

    if not picos:
        _partida("nível do mic", "SEM BLOCOS — nada chegou")
        return
    pico = int(max(picos))
    if pico < 50:
        _partida("nível do mic", f"PICO {pico}/32767 — praticamente silêncio")
        print("\n  ATENÇÃO: este microfone não está captando nada.")
        print("  O Jarvis nunca vai acordar. Confira o mute físico do Fifine")
        print("  ou escolha outra entrada com --listar-dispositivos.\n")
    else:
        _partida("nível do mic", f"pico {pico}/32767 — captando")


def listar_dispositivos() -> int:
    print("\nENTRADAS (microfone)")
    for d in microfone.listar_dispositivos():
        if d.canais_entrada:
            marca = " ← padrão do sistema" if d.padrao_entrada else ""
            print(f"  [{d.indice:>2}] {d.nome}{marca}")
    print("\nSAÍDAS (alto-falante)")
    for d in microfone.listar_dispositivos():
        if d.canais_saida:
            marca = " ← padrão do sistema" if d.padrao_saida else ""
            print(f"  [{d.indice:>2}] {d.nome}{marca}")
    print("\nFixe um deles em dispositivo_entrada/dispositivo_saida no config.toml.\n")
    return 0


# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Jarvis — assistente por voz com wake word (Etapa 0.6)."
    )
    p.add_argument("--listar-dispositivos", action="store_true")
    p.add_argument(
        "--teste-ciclo",
        action="store_true",
        help="exercita a máquina de estados sem microfone",
    )
    p.add_argument("--config", type=Path, default=None)
    args = p.parse_args(argv)

    if args.listar_dispositivos:
        return listar_dispositivos()

    try:
        cfg = config.carregar(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"\n{e}\n", file=sys.stderr)
        return 1

    if args.teste_ciclo:
        return teste_ciclo(cfg)
    return conversar(cfg)


if __name__ == "__main__":
    sys.exit(main())
