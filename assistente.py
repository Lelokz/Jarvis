#!/usr/bin/env python3
"""Jarvis — o cliente de voz.

Dorme escutando só o wake word. Ao ouvir "hey Jarvis", cumprimenta, abre uma
janela de 30s e escuta. Sem fala, volta a dormir sozinho.

**Este arquivo é o corpo, não o cérebro** (ESCOPO §4). Ele cuida de ouvir e
falar: microfone, wake word, VAD, Whisper, voz e o ciclo de vida. Quem decide
o que fazer e executa é o Claude Code inteiro (`jarvis/agente/`): este laço
manda texto e recolhe o que ele devolve — fala, pergunta, coisa para a janela
— sem nunca travar o microfone esperando.

É essa divisão que vai permitir um cliente de celular depois sem reescrever
nada: só o transporte muda.

O `etapa0.py` continua existindo e intocado — é o banco de medição de latência
e o `--autoteste`, que é o primeiro diagnóstico quando algo aqui quebrar.
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import datetime as dt
import json
import math
import queue
import signal
import sys
import time
import tomllib
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

import numpy as np

from jarvis import ajustes, config, cronometro, eventos, microfone, som, tts, wakeword
from jarvis.agente import sessoes
from jarvis.agente.agente import Agente, ErroDoAgente, Saida
from jarvis.agente.avisos import AvisosWhatsApp
from jarvis.escola.vigia import Vigia
from jarvis.agente.reflexos import reflexo
from jarvis.cronometro import Tempos
from jarvis.nucleo import recados, relogio
from jarvis.nucleo.atalhos import normalizar
from jarvis.nucleo.whatsapp import WhatsApp
from jarvis.quem_fala import QuemFala, Voz
from jarvis.ponte import protocolo
from jarvis.ponte.servidor import Pedido, Servidor, ServidorOcupado
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
        "voce_disse", "jarvis_disse", "tempos", "atividade", "mostrar",
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
        elif tipo == "atividade":
            print(f"             {'':<8}▸ {ev['texto']}")
        elif tipo == "mostrar":
            linhas = ev["texto"].splitlines()
            titulo = f"{ev['titulo']} — " if ev.get("titulo") else ""
            print(f"             {'':<8}[janela] {titulo}{linhas[0] if linhas else ''}"
                  + (f" (+{len(linhas) - 1} linhas)" if len(linhas) > 1 else ""))
        elif tipo == "tempos":
            print(
                f"             {'':<8}stt {ev['stt_s']:.2f}s · "
                f"claude {ev['nucleo_s']:.2f}s · "
                f"tts {ev['tts_s']:.2f}s · "
                f"latência {ev['latencia_s']:.2f}s"
            )


# "Dorme aí": ele volta a dormir na hora, sem esperar a janela de 30s. Para
# quando você vai conversar com outra pessoa e não quer que ele responda.
#
# Fica no CLIENTE, e não no núcleo: dormir e acordar é o ciclo do microfone, e
# o núcleo não sabe o que é isso (ESCOPO §4). Lista fechada contra a fala
# INTEIRA, já normalizada (sem acento, pontuação e artigo): "dorme" casa,
# "o arquivo dorme na pasta" não. Errar aqui custa pouco — no pior caso ele
# dorme e você chama de novo.
COMANDOS_DE_DORMIR = {
    "dorme", "dorme ai", "dorme jarvis", "jarvis dorme", "vai dormir",
    "pode dormir", "pode ir dormir", "vai dormir jarvis", "pode dormir jarvis",
    "dormir", "descansa", "vai descansar", "pode descansar",
    "tchau", "tchau jarvis", "valeu pode dormir", "obrigado pode dormir",
    "volta dormir", "volta pra dormir", "volta para dormir",
}


def e_comando_de_dormir(texto: str) -> bool:
    return normalizar(texto) in COMANDOS_DE_DORMIR


# "Para" com o Claude no meio de uma tarefa interrompe a tarefa. Sem tarefa,
# "para" é o reflexo de pausar a música. A fala INTEIRA, como o "dorme aí".
COMANDOS_DE_PARAR = {
    "para", "parar", "para jarvis", "jarvis para", "para tudo", "cancela",
    "cancela isso", "esquece", "esquece isso", "deixa", "deixa pra la", "chega",
    "pode parar", "para ai", "para isso",
}


def e_pedido_de_parar(texto: str) -> bool:
    # "Para, para." repetido também vale (aconteceu no primeiro teste por voz).
    palavras = normalizar(texto).split()
    sem_repetir = [p for i, p in enumerate(palavras) if i == 0 or p != palavras[i - 1]]
    return " ".join(sem_repetir) in COMANDOS_DE_PARAR


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
        agente: Agente,
        registrador: Registrador,
        voz_friday: tts.Voz | None = None,
        portao,
        dispositivo_saida: int | None,
        emissor: eventos.Emissor | None = None,
        avisos: AvisosWhatsApp | None = None,
    ) -> None:
        self.cfg = cfg
        self.agente = agente
        self.avisos = avisos
        # Pergunta do Claude esperando a resposta falada: (a saída, até quando
        # a resposta pode COMEÇAR). Depois do prazo vale "não respondeu".
        self._pergunta: tuple[Saida, float] | None = None
        # Vai junto da próxima fala para o Claude (o WhatsApp que acabou de
        # ser anunciado, para "responde que eu chego às oito").
        self._contexto = ""
        # Quem está falando (a voz do Léo ou outra): as travas do agente olham.
        # Sem os arquivos (perfil, modelo), fica desligado e vale como antes.
        try:
            self.quem_fala: QuemFala | None = QuemFala()
            if self.quem_fala.perfil is None:
                self.quem_fala = None
        except Exception as e:
            print(f"  reconhecer a voz: desligado ({e.__class__.__name__}: {e})", flush=True)
            self.quem_fala = None
        self._ultima_voz: tuple[Voz, float] | None = None
        # O pedido em andamento, para medir o tempo quando a resposta chegar.
        self._pedido: tuple[float, object, object] | None = None
        # Onde a voz sai: None = a caixa de som do PC; um número = o cliente
        # da ponte que é um "corpo" (o celular) e fez o último pedido. Volta
        # para o PC quando alguém fala com ele aqui (wake word, janela).
        self._corpo: int | None = None
        # O corpo está no mudo (o botão do app): a resposta vai só em texto.
        self._mudo = False
        # Manda um erro só para quem pediu (a ponte põe aqui; ex.: "nova" no
        # meio de uma tarefa).
        self.avisar_cliente = lambda _id, _motivo: None
        self.vad = detector_vad
        self.ww = detector_ww
        self.transcritor = transcritor
        self.voz = voz
        # As duas personas (25/10/2026): "hey Friday" troca a voz, as frases
        # fixas e a marca no pedido; "hey Jarvis" volta. Sem a Friday no
        # config (ou sem a voz dela), fica tudo como antes.
        self._vozes = {"jarvis": voz, "friday": voz_friday or voz}
        self.persona = "jarvis"
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

    @property
    def persona_cfg(self) -> config.Persona:
        """As frases fixas da persona ativa ("Pois não?" ou "Oi, chefinho!")."""
        if self.persona == "friday" and self.cfg.persona_friday is not None:
            return self.cfg.persona_friday
        return self.cfg.persona

    def trocar_persona(self, nome: str) -> None:
        """Quem responde a partir de agora: voz, frases fixas e o pedido ao
        Claude. Avisa a janela e o app (a cor do átomo)."""
        if nome == "friday" and self.cfg.friday is None:
            nome = "jarvis"
        mudou = nome != self.persona
        self.persona = nome
        self.voz = self._vozes.get(nome, self._vozes["jarvis"])
        self.agente.persona = nome
        if mudou:
            self.registrador.registrar_estado("persona", persona=nome)
            self.emitir_cerebro()

    def acordar(self, score: float) -> None:
        self._corpo = None  # chamaram aqui no PC: a voz volta para a caixa de som
        # Qual palavra acordou: "hey Friday" chama a Friday; "hey Jarvis", ele.
        friday = self.cfg.friday
        self.trocar_persona("friday" if friday is not None and friday.ligada
                            and getattr(self.ww, "ultimo_rotulo", None) == friday.modelo_wake else "jarvis")
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

        self._falar(self.persona_cfg.saudacao)
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
        # A conversa com o Claude NÃO recomeça (pedido do Léo): ele lembra do
        # papo entre um "dorme aí" e outro. O contexto do WhatsApp anunciado,
        # sim, não atravessa o sono.
        self._contexto = ""
        self._mudar_estado("dormindo")
        self.emissor.emitir("dormiu", motivo=motivo)
        self.registrador.registrar_estado("dormiu", motivo=motivo)

    def _renovar(self, rotulo: str) -> None:
        if self._corpo is not None and self.estado is Estado.DORMINDO:
            # Conversa pelo celular: o microfone do PC continua dormindo (ele
            # pode estar fora, com outras pessoas em casa).
            self._mudar_estado("dormindo")
            return
        self.prazo = time.monotonic() + self.cfg.ciclo.janela_s
        self.emissor.emitir("janela", rotulo=rotulo, janela_s=self.cfg.ciclo.janela_s)
        self.registrador.registrar_estado(rotulo, janela_s=self.cfg.ciclo.janela_s)
        self._mudar_estado("ouvindo")

    def _falar(
        self, texto: str, *, acao: str | None = None, perguntando: bool = False,
        opcoes: list[str] | None = None,
    ) -> tts.TemposDaFala:
        """Fala com o portão anti-eco fechado.

        Sem isto o microfone pega a própria voz do Jarvis: o VAD dispara e ele
        se responde, e — pior neste etapa — o wake word pode se ouvir e acordar
        de novo em laço.
        """
        # As opções da pergunta vão junto: a janela mostra como botões.
        extra = {"opcoes": list(opcoes)} if perguntando and opcoes else {}
        if self._corpo is not None:
            return self._falar_no_corpo(texto, acao=acao, perguntando=perguntando, extra=extra)
        self.portao.fechar_portao()

        def ao_comecar() -> None:
            # Texto, estado "falando" e voz saem juntos: antes o texto chegava
            # na janela uns 2 s antes do som (o tempo de gerar a voz).
            self._mudar_estado("falando")
            self.emissor.emitir(
                "jarvis_disse", texto=texto, acao=acao, perguntando=perguntando, **extra
            )

        try:
            return tts.falar(self.voz, texto, dispositivo=self.dispositivo_saida,
                             ao_comecar=ao_comecar)
        finally:
            time.sleep(self.guarda_s)
            self.portao.abrir_portao()
            self.ww.reiniciar()
            self.vad.reiniciar()

    def _falar_no_corpo(
        self, texto: str, *, acao: str | None, perguntando: bool, extra: dict
    ) -> tts.TemposDaFala:
        """A voz vai para o celular, pedaço por pedaço, pelos eventos "voz"
        da ponte. Sem portão: o microfone do PC não ouve o celular. No mudo,
        só o texto: a voz nem é gerada."""
        if self._mudo:
            self.emissor.emitir("jarvis_disse", texto=texto, acao=acao, perguntando=perguntando,
                                **extra)
            return tts.TemposDaFala(primeiro_audio_s=0.0, sintese_total_s=0.0,
                                    reproducao_s=0.0, duracao_audio_s=0.0)
        inicio = time.monotonic()
        primeiro: float | None = None
        duracao = 0.0
        try:
            for trecho in self.voz.sintetizar(texto):
                if primeiro is None:
                    primeiro = time.monotonic() - inicio
                    self._mudar_estado("falando")
                    self.emissor.emitir("jarvis_disse", texto=texto, acao=acao,
                                        perguntando=perguntando, **extra)
                self.emissor.emitir("voz", para=self._corpo, taxa=trecho.taxa,
                                    pcm=base64.b64encode(trecho.pcm).decode("ascii"))
                duracao += len(trecho.pcm) / 2 / trecho.taxa
        finally:
            if primeiro is None:  # a voz falhou: o texto chega mesmo assim
                self.emissor.emitir("jarvis_disse", texto=texto, acao=acao,
                                    perguntando=perguntando, **extra)
            self.emissor.emitir("voz", para=self._corpo, fim=True)
        total = time.monotonic() - inicio
        return tts.TemposDaFala(primeiro_audio_s=primeiro or 0.0, sintese_total_s=total,
                                reproducao_s=0.0, duracao_audio_s=duracao)

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
                self._mudar_estado("pensando" if self.agente.ocupado else "ouvindo")
            agora = time.monotonic()
            # A pergunta do Claude venceu sem resposta: vale "não respondeu".
            # Com o VAD em fala, espera a frase: ela começou dentro do prazo.
            if self._pergunta is not None and agora >= self._pergunta[1] \
                    and not self.vad.falando:
                saida, _ = self._pergunta
                self._pergunta = None
                self.registrador.registrar_estado("pergunta_sem_resposta", pergunta=saida.texto)
                self.agente.responder(saida, None)
                self._mudar_estado("pensando")
            # Nunca dormir no meio de uma frase, nem com o Claude trabalhando
            # ou esperando resposta: a resposta dele tem que ser ouvida.
            if agora >= self.prazo and not self.vad.falando and \
                    not self.agente.ocupado and self._pergunta is None \
                    and self.agente.saidas.empty():
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

        self._corpo = None
        self._responder(
            transcricao.texto, origem="voz", segmento=segmento, transcricao=transcricao,
            voz=self._identificar(segmento.audio),
        )

    def _responder(
        self,
        texto: str,
        *,
        origem: str,
        segmento=None,
        transcricao=None,
        voz: Voz | None = None,
    ) -> None:
        """Entrega a fala ao Claude (ou a um reflexo) e volta a ouvir.

        Um caminho só para voz e para texto digitado. **Não espera a
        resposta:** uma tarefa pode levar minutos e perguntar no meio, e o
        microfone tem que continuar ouvindo ("para", a resposta da pergunta).
        O que o Claude devolve chega por `atender_agente()`.
        """
        # Tela bloqueada: só o Léo (decisão dele, 23/10/2026). Outra voz nem
        # chega ao Claude. Digitado (voz None) vale como ele.
        if voz is not None and voz.quem != "leo":
            from jarvis.nucleo import tela
            if tela.bloqueada():
                self.registrador.registrar_estado("tela_bloqueada_outra_voz", texto=texto, quem=voz.quem)
                self.dormir("tela bloqueada: só o dono")
                return
        self._mudar_estado("pensando")
        self.emissor.emitir("voce_disse", texto=texto, origem=origem)

        # 1. A resposta a uma pergunta dele (permissão, dúvida).
        if self._pergunta is not None:
            saida, _ = self._pergunta
            self._pergunta = None
            self.registrador.registrar_estado("resposta_a_pergunta",
                                              pergunta=saida.texto, resposta=texto)
            self.agente.responder(saida, texto, voz)
            self._mudar_estado("pensando")
            return

        # 2. "Dorme aí". Com tarefa em andamento ela continua, e o resultado
        #    acorda o Jarvis para ser dito.
        if e_comando_de_dormir(texto):
            self.registrador.registrar_estado("pediu_para_dormir", texto=texto)
            self._falar(self.persona_cfg.indo_dormir)
            self.dormir("você pediu")
            return

        # 3. Com o Claude trabalhando: "para" interrompe; o resto entra na
        #    tarefa (medido: ele incorpora a fala nova).
        if self.agente.ocupado:
            if e_pedido_de_parar(texto):
                self.registrador.registrar_estado("interrompeu", texto=texto)
                self.agente.interromper()
            else:
                self.registrador.registrar_estado("fala_no_meio", texto=texto)
                contexto, self._contexto = self._contexto, ""
                self.agente.pedir(texto, origem, contexto, voz)
            self._mudar_estado("pensando")
            return

        # 4. Reflexo: pausa, volta, volume. 0 s, sem o Claude.
        r = reflexo(texto, self.cfg.midia.limite_confirmacao, self.cfg.midia.passo_volume)
        if r is not None:
            self.acoes += 1 if r.acao else 0
            self.registrador.registrar_estado("decisao", resposta=r.fala, acao=r.acao,
                                              origem="reflexo", dito=texto)
            self._falar(r.fala, acao=r.acao)
            self._renovar("janela reiniciada")
            return

        # 5. O Claude.
        contexto, self._contexto = self._contexto, ""
        if origem in ("voz", "texto") and self._primeira_da_manha():
            nota = ("[Primeira conversa do dia no PC, de manhã: junto com o que ele "
                    "pediu, dê o briefing do \"Bom dia\" (CLAUDE.md da casa), curto.]")
            contexto = "\n".join(p for p in (nota, contexto) if p)
        self.registrador.registrar_estado("pedido", texto=texto, origem=origem,
                                          contexto=contexto or None)
        self._pedido = (time.monotonic(), segmento, transcricao)
        self.agente.pedir(texto, origem, contexto, voz)

    def _primeira_da_manha(self) -> bool:
        """O briefing da manhã: só no PC (o Léo de manhã vai para a escola; no fim
        de semana acorda e vai direto para o computador), no primeiro pedido ao
        Claude do dia, antes das 14h. O dia do último fica em `.ultimo-briefing`,
        na casa, para religar o Jarvis não repetir."""
        agora = datetime.now()
        if agora.hour >= 14:
            return False
        marca = self.agente.casa / ".ultimo-briefing"
        hoje = agora.date().isoformat()
        try:
            if marca.read_text().strip() == hoje:
                return False
        except OSError:
            pass
        marca.write_text(hoje + "\n")
        return True

    # -- o que o Claude devolve --------------------------------------------

    def atender_agente(self) -> None:
        """Recolhe o que o Claude mandou. Chamado a cada volta do laço."""
        while True:
            try:
                saida = self.agente.saidas.get_nowait()
            except queue.Empty:
                return
            self._saida(saida)

    def _saida(self, s: Saida) -> None:
        if s.tipo == "parcial":
            # O texto enquanto ele escreve: só para a janela (fora do log e do
            # histórico). A fala continua saindo só com o texto inteiro.
            if s.janela == "descartar":
                self.emissor.emitir("escrevendo", fim=True, descartar=True)
            else:
                self._escreveu = True
                self.emissor.emitir("escrevendo", bloco=int(s.titulo or 0), delta=s.texto)
            return
        if s.tipo == "atividade":
            self.acoes += 1
            self.registrador.registrar_estado("atividade", texto=s.texto)
            self.emissor.emitir("atividade", texto=s.texto)
        elif s.tipo == "mostrar":
            self.registrador.registrar_estado("mostrar", titulo=s.titulo, texto=s.texto)
            self.emissor.emitir("mostrar", titulo=s.titulo, texto=s.texto)
        elif s.tipo == "falar":
            self._acordar_se_dormindo()
            self.registrador.registrar_estado("fala_no_meio_da_tarefa", fala=s.texto)
            self._falar(s.texto)
            self._mudar_estado("pensando")
        elif s.tipo == "perguntar":
            self._acordar_se_dormindo()
            fala = _pergunta_falada(s.texto, s.opcoes)
            self.registrador.registrar_estado("pergunta", fala=fala, opcoes=s.opcoes)
            self._falar(fala, perguntando=True, opcoes=s.opcoes)
            # O prazo conta de quando ele TERMINA de perguntar.
            self._pergunta = (s, time.monotonic() + self.cfg.agente.validade_pergunta_s)
            self._renovar("pergunta feita")
        elif s.tipo == "desbloqueio":
            # O pedido de desbloquear: o app mostra "Desbloquear o PC?" (se
            # estiver conectado na hora; fechado, busca em /desbloqueio).
            from jarvis.nucleo import desbloqueio
            pedido = desbloqueio.pendente()
            if pedido is not None:
                self.registrador.registrar_estado("pediu_desbloqueio", id=pedido["id"])
                self.emissor.emitir("desbloqueio", id=pedido["id"], expira_em=pedido["expira_em"])
        elif s.tipo == "fim":
            self._fim(s)
            if getattr(self.agente, "bloquear_ao_terminar", False):
                # Só agora, com a resposta já falada (antes bloqueava no meio).
                self.agente.bloquear_ao_terminar = False
                from jarvis.nucleo import tela
                self.registrador.registrar_estado("bloqueou_a_tela")
                tela.bloquear()
            # O que ainda estava "escrevendo" (interrompido, sem fala) fica
            # como texto normal na janela.
            self._fim_da_escrita()
            self.atualizar_aviso()
        elif s.tipo == "sessao":
            # Chat novo ou retomado: a janela troca a conversa que mostra.
            falas = []
            if s.janela == "continuada":
                try:
                    falas = sessoes.falas(self.agente.casa, s.texto)
                except Exception as e:
                    self.registrador.registrar_estado("conversa_erro", erro=str(e))
            self.registrador.registrar_estado("conversa", id=s.texto, como=s.janela)
            self.emissor.emitir("conversa_atual", id=s.texto, falas=falas)
        elif s.tipo == "erro":
            fala = {"limite": self._fala_de_limite(self.agente.limite.volta_em),
                    "offline": self.persona_cfg.sem_internet}.get(
                        s.texto, self.persona_cfg.cerebro_falhou)
            self.registrador.registrar_estado("erro_do_claude", tipo=s.texto, detalhe=s.titulo)
            self._fim_da_escrita()
            self._pedido = None
            self._acordar_se_dormindo()
            self._falar(fala)
            self.atualizar_aviso()
            self._renovar("janela reiniciada")

    def _fim_da_escrita(self) -> None:
        """Fecha o texto em pedaços do turno, se houve (beta 0.5)."""
        if getattr(self, "_escreveu", False):
            self._escreveu = False
            self.emissor.emitir("escrevendo", fim=True, descartar=False)

    def _fim(self, s: Saida) -> None:
        pedido, self._pedido = self._pedido, None
        claude_s = time.monotonic() - pedido[0] if pedido else 0.0
        if s.janela:
            self.emissor.emitir("mostrar", titulo="", texto=s.janela)
        fala_texto = self.persona_cfg.parei if s.interrompido else s.texto
        self.registrador.registrar_estado("resposta", fala=fala_texto, janela=s.janela,
                                          interrompido=s.interrompido, claude_s=round(claude_s, 2))
        if not fala_texto:
            # O Claude achou que não era com ele (vídeo, TV, conversa com
            # outra pessoa): fica calado e NÃO reinicia a janela de 30 s, para
            # voltar a dormir sozinho no tempo de sempre.
            self.emissor.emitir("ignorado", texto="")
            if self.estado is Estado.ACORDADO:
                self._mudar_estado("ouvindo")
            return
        self._acordar_se_dormindo()
        fala = self._falar(fala_texto)

        # Tempos e .wav só existem para o que foi FALADO: texto digitado não
        # tem segmento, nem Whisper, nem espera de silêncio para medir.
        if pedido and pedido[1] is not None and pedido[2] is not None:
            segmento, transcricao = pedido[1], pedido[2]
            tempos = Tempos(
                duracao_segmento_s=segmento.duracao_total_s,
                espera_silencio_s=segmento.espera_silencio_s,
                stt_s=transcricao.segundos,
                nucleo_s=claude_s,
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
                nucleo_s=claude_s,
                tts_s=fala.primeiro_audio_s,
                latencia_s=tempos.latencia_percebida_s,
            )
        self.atualizar_aviso()
        # A janela reinicia quando ELE termina de responder, não quando você
        # termina de falar.
        self._renovar("janela reiniciada")

    def _acordar_se_dormindo(self) -> None:
        """O Claude terminou ou perguntou com o Jarvis dormindo (o Léo disse
        "dorme aí" no meio da tarefa): acorda sem saudação para dizer. Na
        conversa pelo celular, não: a resposta vai para lá."""
        if self.estado is Estado.DORMINDO and self._corpo is None:
            self._acordar_por_texto()

    def _fala_de_limite(self, volta_em: float | None) -> str:
        p = self.persona_cfg
        if not volta_em:
            return p.limite_acabou_sem_hora
        volta = dt.datetime.fromtimestamp(volta_em)
        hora = relogio.hora_falada(volta).removeprefix("É ").removeprefix("São ").rstrip(".")
        hora = ("ao " if hora.startswith("meio-dia") else "à " if hora.startswith(("meia", "uma"))
                else "às ") + hora
        minutos = max(1, round((volta_em - dt.datetime.now().timestamp()) / 60))
        h, m = divmod(minutos, 60)
        falta = (f"{h} hora{'s' if h > 1 else ''}" if h else "") + \
                (" e " if h and m else "") + (f"{m} minuto{'s' if m > 1 else ''}" if m else "")
        return p.limite_acabou.format(hora=hora, falta=falta)

    # -- aviso do cérebro de nuvem (limite / sem internet) ---------------------

    def atualizar_aviso(self, conferir_internet: bool = False) -> None:
        """Manda para a janela o estado do Claude, só quando muda.

        `conferir_internet` é o relógio de 30 s do laço: sem ele, o aviso de
        "sem internet" só sairia no próximo pedido, mesmo com a rede de volta.
        """
        if conferir_internet:
            self.agente.conferir_internet()
        # O uso da assinatura (a página de Ajustes da janela), só quando muda.
        uso = getattr(self.agente, "uso", {})
        if uso and uso != getattr(self, "_ultimo_uso", None):
            self._ultimo_uso = dict(uso)
            self.emissor.emitir("uso", **uso)
        s = self.agente.situacao()
        chave = (s.get("tipo"), s.get("volta_em") if s.get("tipo") == "limite" else None)
        if chave == getattr(self, "_ultimo_aviso", None):
            return
        self._ultimo_aviso = chave
        # "situacao", e não "tipo": o emitir() já usa `tipo` como nome do evento.
        self.emissor.emitir("aviso", situacao=s.get("tipo", "ok"),
                            volta_em=s.get("volta_em"), uso_5h=s.get("uso_5h"))

    # -- WhatsApp: chegou mensagem ------------------------------------------

    def anunciar_whatsapp(self) -> None:
        """Fala o que chegou no WhatsApp e fica ouvindo, para o Léo poder
        responder sem dizer "hey Jarvis" ("responde que eu chego às oito")."""
        # Com uma pergunta do Claude no ar, o aviso espera: a próxima fala do
        # Léo é a resposta dela, e um aviso no meio embaralharia as duas.
        if self.avisos is None or self._pergunta is not None:
            return
        aviso = self.avisos.checar()
        if aviso is None:
            return
        # Conversa que o Léo está tendo pelo celular: só aparece na janela.
        for texto in aviso.mostrar:
            self.registrador.registrar_estado("whatsapp_so_janela", fala=texto)
            self.emissor.emitir("jarvis_disse", texto=texto, acao="whatsapp:silenciosa",
                                perguntando=False)
        if not aviso.falar:
            return
        # O aviso é SEMPRE na caixa de som do PC, nunca no celular (decisão do
        # Léo: "imagina no meio da aula"; lá o próprio WhatsApp já notifica).
        # A conversa pelo celular continua depois, no celular.
        corpo, self._corpo = self._corpo, None
        try:
            self._contexto = aviso.contexto
            dormia = self.estado is Estado.DORMINDO
            if dormia and aviso.ouvir:
                self._acordar_por_texto()
            for fala in aviso.falar:
                self.registrador.registrar_estado("whatsapp_recebida", fala=fala, ouvir=aviso.ouvir)
                self._falar(fala, acao="whatsapp:recebida")
            if aviso.ouvir:
                self._renovar("janela aberta")
            elif dormia:
                # Som tocando: avisou e volta a dormir, sem ouvir o vídeo.
                self._mudar_estado("dormindo")
        finally:
            self._corpo = corpo

    # -- texto digitado (Etapa 6) ------------------------------------------

    def atender_texto(self, texto: str) -> None:
        """Um pedido digitado num cliente, atendido como se tivesse sido falado.

        **Roda na thread de áudio, nunca na do socket.** O ciclo guarda estado
        de conversa — a pergunta do Claude esperando resposta — e duas threads
        nele fariam uma resposta falada e uma digitada se atropelarem.

        Decisão do Léo: digitar acorda mesmo dormindo, e a resposta sai na voz.
        Sem a saudação: ela existe para confirmar que o wake word pegou, e aqui
        o próprio texto já é o comando.
        """
        self._corpo = None
        if self.estado is Estado.DORMINDO:
            self._acordar_por_texto()
        self.registrador.registrar_estado("texto_digitado", texto=texto)
        self._responder(texto, origem="texto")

    def emitir_som(self) -> None:
        """Os aparelhos de som para os Ajustes da janela."""
        if not getattr(self, "som_ativo", False):
            return
        try:
            self.emissor.emitir("som", **som.listar())
        except Exception:
            pass  # o servidor de som piscou: a janela pede de novo ao abrir os Ajustes

    def do_recado(self, recado: str) -> None:
        """Chegou a hora de um recado que o Jarvis deixou para si mesmo
        (jarvis/nucleo/recados.py): vira um pedido, e ele faz do jeito dele."""
        self.registrador.registrar_estado("recado", texto=recado[:300])
        self._responder(f"[Chegou a hora de um recado que VOCÊ deixou para si mesmo: {recado}] "
                        "Faça o que anotou.", origem="recado")

    def do_grupo(self, tipo: str, valor: str) -> None:
        """O que o Jarvis do grupo da família manda para cá (jarvis/grupo)."""
        if tipo == "notificar":
            self.emissor.emitir("notificacao")
        elif tipo == "aprovacao":
            from jarvis.nucleo import aprovacoes
            for a in aprovacoes.pendentes():
                if a["id"] == valor:
                    self.registrador.registrar_estado("pedido_do_grupo", quem=a["quem"], pedido=a["pedido"])
                    self.emissor.emitir("aprovacao", id=a["id"], quem=a["quem"], pedido=a["pedido"])
        elif tipo == "executar":
            # Aprovado pelo dono no celular: o Jarvis do PC faz, como um pedido digitado.
            self.registrador.registrar_estado("grupo_aprovado", texto=valor[:300])
            self._responder(valor, origem="grupo")

    def emitir_ajustes(self) -> None:
        # tem_escola: este PC está ligado a uma escola (jarvis/escola). Sem
        # ela, a janela e o app nem mostram o interruptor.
        from jarvis.escola.__main__ import RESUMO
        import socket
        self.emissor.emitir("ajustes", **ajustes.ler(), tem_escola=RESUMO.exists(), pc=socket.gethostname())

    def emitir_cerebro(self) -> None:
        cor = self.cfg.friday.cor if self.persona == "friday" and self.cfg.friday else ""
        self.emissor.emitir("cerebro", persona=self.persona, cor_persona=cor, **self.agente.cerebro)

    def atender_pedido(self, pedido: Pedido) -> None:
        """Um pedido da ponte. Da janela (sem voz própria), é o texto
        digitado de sempre. De um corpo (o celular), é atendido LÁ: a voz sai
        nele e o PC continua dormindo. Roda na thread de áudio."""
        if pedido.tipo in ("nova", "continuar"):
            ok = self.agente.nova_conversa() if pedido.tipo == "nova" \
                else self.agente.continuar_conversa(pedido.valor)
            if not ok:
                self.avisar_cliente(pedido.cliente, "Espera ele terminar o pedido (ou diz "
                                                    "\"para\") pra trocar de conversa.")
            return
        if pedido.tipo == "parar":
            # O botão Parar da janela: o mesmo que dizer "para".
            if self._pergunta is not None:
                saida, _ = self._pergunta
                self._pergunta = None
                self.agente.responder(saida, None)
            if self.agente.ocupado:
                self.registrador.registrar_estado("interrompeu", texto="(botão Parar)")
                self.agente.interromper()
            return
        if pedido.tipo == "som":
            try:
                escolha = json.loads(pedido.valor or "{}")
            except ValueError:
                return
            if escolha and getattr(self, "som_ativo", False):
                som.guardar(escolha.get("saida"), escolha.get("entrada"))
                som.aplicar()
                if "entrada" in escolha and hasattr(self.portao, "trocar"):
                    self.portao.trocar()  # a saída vale já na próxima fala
                self.registrador.registrar_estado("som", **som.escolha())
            self.emitir_som()
            return
        if pedido.tipo == "ajustes":
            try:
                novos = json.loads(pedido.valor or "{}")
            except ValueError:
                return
            if novos:
                self.registrador.registrar_estado("ajustes", **ajustes.mudar(**novos))
            self.emitir_ajustes()
            return
        if pedido.tipo == "cerebro":
            try:
                escolha = json.loads(pedido.valor)
            except ValueError:
                return
            if escolha.get("persona"):
                self.trocar_persona(escolha["persona"])
            if escolha.get("modelo") or escolha.get("esforco"):
                self.agente.definir_cerebro(escolha.get("modelo"), escolha.get("esforco"))
            self.registrador.registrar_estado("cerebro", **self.agente.cerebro)
            self.emitir_cerebro()
            return
        if pedido.anexos:
            # Vai junto do pedido para o Claude, como o contexto do WhatsApp.
            nota = ("[Anexos que o usuário mandou, já no PC (imagem: abra com o Read; "
                    "vídeo: tire alguns quadros com ffmpeg e olhe): "
                    + ", ".join(pedido.anexos) + "]")
            self._contexto = "\n".join(p for p in (self._contexto, nota) if p)
        if not pedido.voz:
            if pedido.tipo == "falar":
                self.atender_texto(pedido.valor)
            return
        self._corpo = pedido.cliente
        self._mudo = pedido.mudo
        if pedido.tipo == "falar":
            self.registrador.registrar_estado("texto_do_celular", texto=pedido.valor)
            self._responder(pedido.valor, origem="celular")
            return
        # "ouvir": a fala gravada no celular, num arquivo que a porta remota
        # deixou na pasta da ponte. Lê, apaga e transcreve.
        caminho = Path(pedido.valor)
        try:
            pcm = caminho.read_bytes()
        except OSError:
            pcm = b""
        finally:
            caminho.unlink(missing_ok=True)
        audio = np.frombuffer(pcm[: len(pcm) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768
        self._mudar_estado("pensando")
        transcricao = self.transcritor.transcrever(audio) if len(audio) >= 1600 else None
        if transcricao is None or not transcricao.texto:
            self.vazias += 1
            self.registrador.registrar_descarte("audio do celular vazio",
                                                {"duracao_s": round(len(audio) / 16000, 3)})
            self._falar("Não peguei o áudio. Fala de novo?")
            self._mudar_estado("dormindo" if self.estado is Estado.DORMINDO else "ouvindo")
            return
        self.registrador.registrar_estado("fala_do_celular", texto=transcricao.texto,
                                          stt_s=round(transcricao.segundos, 2))
        self._responder(transcricao.texto, origem="celular", voz=self._identificar(audio))

    def _identificar(self, audio: np.ndarray) -> Voz | None:
        """Quem falou. Fala curta ("sim", "pode") não dá para reconhecer:
        herda a voz da última fala reconhecida, se foi há menos de 2 min (a
        resposta curta é de quem fez o pedido)."""
        if self.quem_fala is None:
            return None
        try:
            voz = self.quem_fala.quem(audio)
        except Exception as e:
            self.registrador.registrar_estado("voz_erro", erro=f"{e.__class__.__name__}: {e}")
            return None
        agora = time.monotonic()
        herdou = False
        if voz.quem == "curta" and self._ultima_voz and agora - self._ultima_voz[1] < 120:
            voz, herdou = Voz(self._ultima_voz[0].quem, self._ultima_voz[0].nota, voz.segundos), True
        elif voz.quem != "curta":
            self._ultima_voz = (voz, agora)
        self.registrador.registrar_estado("voz", quem=voz.quem, nota=round(voz.nota, 3),
                                          segundos=round(voz.segundos, 2), herdou=herdou)
        return voz

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
        # "Hey Friday" no mesmo detector (divide o mel e o embedding).
        extras={cfg.friday.modelo_wake: cfg.friday.limiar} if cfg.friday and cfg.friday.ligada else None,
    )
    _partida("wake word", detector_ww.descricao, detector_ww.segundos_de_carga)

    transcritor = Transcritor(cfg.stt)
    _partida("Whisper", transcritor.descricao, transcritor.segundos_de_carga)
    _partida("aquecimento", "(1ª inferência, descartada)", transcritor.aquecer())

    voz = tts.criar_voz(cfg.tts, cfg.dir_vozes)
    _partida("voz", voz.nome, voz.segundos_de_carga)
    voz_friday = None
    if cfg.friday is not None and cfg.friday.ligada:
        voz_friday = tts.criar_voz_friday(cfg.tts, cfg.friday.socket, cfg.dir_vozes)
        _partida("voz da Friday", voz_friday.nome, voz_friday.segundos_de_carga)

    w = cfg.whatsapp
    whatsapp = WhatsApp(w.banco, w.api, w.avisar_grupos) if w.ativo else None
    agente = Agente(cfg.agente, cfg.persona.nome, whatsapp=whatsapp, persona_cfg=cfg.persona)

    # O Claude Code sobe AQUI, e não no primeiro pedido: o "pronto" tem que
    # ser verdade. A mensagem antes é de propósito (terminal parado sem
    # explicação parece travado).
    aviso = "  Claude           abrindo o Claude Code..."
    # No terminal o aviso é reescrito no lugar; num log ele fica como linha
    # própria. O "\r" não apaga nada quando a saída não é um terminal, e sem
    # esta checagem o log sai com os dois textos grudados na mesma linha.
    terminal = sys.stdout.isatty()
    print(aviso, end="" if terminal else "\n", flush=True)
    segundos = agente.iniciar()
    if terminal:
        print("\r" + " " * len(aviso) + "\r", end="")
    _partida("Claude", f"{cfg.agente.modelo} ({cfg.agente.effort}), Claude Code inteiro, "
                       f"modo {cfg.agente.modo_permissao}", segundos)

    # Os nomes do atalhos.toml vão para o Whisper como vocabulário. Medido:
    # sem vocabulário 4/15 dos nomes sobrevivem à fala rápida, com 9/15, sem
    # custo de latência.
    nomes = _nomes_do_vocabulario(cfg.raiz / "atalhos.toml")
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

    return detector_vad, detector_ww, transcritor, voz, agente, voz_friday


def _nomes_do_vocabulario(caminho: Path) -> list[str]:
    try:
        with caminho.open("rb") as f:
            return list(tomllib.load(f).keys())
    except (OSError, tomllib.TOMLDecodeError):
        return []


def _pergunta_falada(pergunta: str, opcoes: list[str]) -> str:
    """A pergunta, com as opções ditas quando ela não as diz sozinha."""
    nomes = [o for o in opcoes if o]
    simples = {normalizar(o) for o in nomes} <= {"sim", "nao", "pode", "cancelar", "nao pode"}
    ditas = all(normalizar(o) in normalizar(pergunta) for o in nomes)
    if not nomes or simples or ditas:
        return pergunta
    lista = ", ".join(nomes[:-1]) + " ou " + nomes[-1] if len(nomes) > 1 else nomes[0]
    return f"{pergunta} {lista}?"


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
        detector_vad, detector_ww, transcritor, voz, agente, voz_friday = _montar(cfg)
    except (ErroDeCuda, ErroDoAgente, wakeword.ModeloAusente, FileNotFoundError) as e:
        print(f"\n{e}\n", file=sys.stderr)
        return 1

    ciclo = Ciclo(
        cfg,
        detector_vad=detector_vad,
        detector_ww=detector_ww,
        transcritor=transcritor,
        voz=voz,
        voz_friday=voz_friday,
        agente=agente,
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
    # Sem aparelho fixo no config.toml: vale o que foi escolhido nos Ajustes
    # da janela (beta 0.6.0), pelo servidor de som do Linux (jarvis/som.py).
    usar_som = not cfg.audio.dispositivo_entrada.strip() and not cfg.audio.dispositivo_saida.strip() \
        and som.disponivel()
    if usar_som:
        som.aplicar()
        indice_entrada = indice_saida = som.DISPOSITIVO
        lista = som.listar()
        _partida("microfone", next((e["nome"] for e in lista["entradas"] if e["id"] == lista["entrada"]),
                                   f"{lista['padrao_entrada']} (padrão do sistema)"))
    else:
        _partida("microfone", microfone.nome_do_dispositivo(indice_entrada, entrada=True))

    try:
        detector_vad, detector_ww, transcritor, voz, agente, voz_friday = _montar(cfg)
    except ErroDeCuda as e:
        print(f"\nCUDA não subiu:\n{e}\n", file=sys.stderr)
        return 1
    except (ErroDoAgente, wakeword.ModeloAusente, FileNotFoundError) as e:
        print(f"\n{e}\n", file=sys.stderr)
        return 1

    registrador = Registrador.criar(cfg, prefixo="jarvis")
    emissor = _emissor_de_terminal(cfg)
    ponte = _abrir_ponte(cfg, registrador, emissor)
    if ponte is not None:
        # A seção de memória e a barra lateral da janela pedem por aqui. Só
        # leem arquivos: rodam na thread da ponte sem tocar na conversa.
        ponte.provedor_memoria = agente.memoria_para_janela
        ponte.provedor_conversas = lambda: sessoes.listar(agente.casa)
        ponte.provedor_conversa = lambda sessao: sessoes.falas(agente.casa, sessao)
        ponte.provedor_renomear = lambda sessao, titulo: sessoes.renomear(agente.casa, sessao, titulo)
        ponte.provedor_apagar = lambda sessao: sessoes.apagar(agente.casa, sessao)
        ponte.provedor_fixar = lambda sessao, sim: sessoes.fixar(agente.casa, sessao, sim)

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
                voz_friday=voz_friday,
                agente=agente,
                registrador=registrador,
                portao=mic,
                dispositivo_saida=indice_saida,
                emissor=emissor,
                avisos=AvisosWhatsApp(agente.whatsapp, cfg.persona, cfg.whatsapp.ler_conteudo,
                                      lambda: agente.enviados_whats),
            )
            if ponte is not None:
                ciclo.avisar_cliente = ponte.avisar
            ciclo.som_ativo = usar_som
            ciclo.emitir_cerebro()
            ciclo.emitir_som()
            ciclo.emitir_ajustes()
            print(REGUA)
            _linha("dormindo", 'diga "hey Jarvis"  (ctrl+c encerra)')

            ciclo.atualizar_aviso()
            proximo_aviso = time.monotonic() + 30
            # Escola (Estudante Online): lê sozinha 3x por dia. O que
            # for novo vira notificação, sem voz (decisão do Léo).
            Vigia().start()
            # O Jarvis no grupo da família (WhatsApp): só com o grupo ligado nos Ajustes.
            grupo = None
            if agente.whatsapp is not None:
                from jarvis.grupo.familia import GrupoFamilia
                grupo = GrupoFamilia(agente.whatsapp, agente.binario, cfg.agente.modelo_rapido or "sonnet")
                grupo.start()
            proximo_whats = time.monotonic() + cfg.whatsapp.intervalo_s
            while True:
                if time.monotonic() >= proximo_aviso:
                    ciclo.atualizar_aviso(conferir_internet=True)
                    proximo_aviso = time.monotonic() + 30
                    # O relógio interno: recados que ele deixou para si mesmo.
                    for recado in recados.vencidos(agente.casa / recados.NOME):
                        ciclo.do_recado(recado)
                # Nunca no meio de você falando: espera a frase acabar.
                if time.monotonic() >= proximo_whats and not ciclo.vad.falando:
                    ciclo.anunciar_whatsapp()
                    proximo_whats = time.monotonic() + cfg.whatsapp.intervalo_s
                do_grupo = grupo.pegar() if grupo is not None else None
                if do_grupo is not None:
                    ciclo.do_grupo(*do_grupo)
                bloco = mic.ler_bloco()
                if bloco is not None:
                    ciclo.passo(bloco)
                # O que o Claude devolveu (fala, pergunta, janela). Nunca no
                # meio de você falando: espera a frase acabar.
                if not ciclo.vad.falando:
                    ciclo.atender_agente()
                # Texto digitado num cliente. Atendido AQUI, na thread de áudio,
                # e só com o VAD fora de fala: quem digita enquanto fala espera
                # a frase acabar, em vez de ter a própria voz cortada.
                if ponte is not None and not ciclo.vad.falando:
                    pedido = ponte.proximo_pedido()
                    if pedido is not None:
                        ciclo.atender_pedido(pedido)

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
        # Fecha o Claude Code. A conversa fica salva por ele: ligando de novo
        # em menos de 3 h, ela continua.
        agente.encerrar()
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


def _desligar_como_ctrl_c(*_) -> None:
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    # Ligado pelo jarvis.sh, o assistente roda em segundo plano, e o bash faz
    # programa em segundo plano IGNORAR o ctrl+c. Então o "desligar" manda
    # SIGTERM, e ele vira o mesmo ctrl+c de sempre: fecha o microfone, apaga
    # o socket e grava o resumo, em vez de morrer no meio.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, _desligar_como_ctrl_c)
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
