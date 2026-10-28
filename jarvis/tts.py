"""TTS atrás de uma interface.

ESCOPO §4: o Piper é *"peça deliberadamente trocável: manter atrás de uma
interface"*, porque o upgrade previsto é o Kokoro-82M. Trocar de motor deve
ser escrever outra classe `Voz` — sem encostar no etapa0.py.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import sounddevice as sd

from .config import Tts as ConfigTts


@dataclass(frozen=True)
class Trecho:
    pcm: bytes  # int16 cru
    taxa: int
    canais: int


@dataclass(frozen=True)
class TemposDaFala:
    primeiro_audio_s: float  # do pedido até o 1º trecho pronto
    sintese_total_s: float  # só o tempo do motor, sem a reprodução
    reproducao_s: float
    duracao_audio_s: float


class Voz(ABC):
    """Contrato mínimo de um motor de voz.

    Quem implementar deve preencher `segundos_de_carga` no __init__ — é um
    dos custos de partida que a Etapa 0 reporta à parte.
    """

    segundos_de_carga: float = 0.0

    @property
    @abstractmethod
    def nome(self) -> str: ...

    @abstractmethod
    def sintetizar(self, texto: str) -> Iterator[Trecho]: ...


class VozPiper(Voz):
    def __init__(self, cfg: ConfigTts, dir_vozes: Path) -> None:
        self.cfg = cfg
        caminho = dir_vozes / f"{cfg.voz}.onnx"
        if not caminho.is_file():
            raise FileNotFoundError(
                f"Voz não encontrada: {caminho}\n"
                f"  Baixe com:\n"
                f"    python -m piper.download_voices {cfg.voz} "
                f"--data-dir {dir_vozes}"
            )

        from piper import PiperVoice, SynthesisConfig

        inicio = time.monotonic()
        self._voz = PiperVoice.load(str(caminho))
        self.segundos_de_carga = time.monotonic() - inicio
        # length_scale: maior = mais devagar.
        self._sintese = SynthesisConfig(length_scale=cfg.velocidade)

    @property
    def nome(self) -> str:
        return self.cfg.voz

    def sintetizar(self, texto: str) -> Iterator[Trecho]:
        for chunk in self._voz.synthesize(texto, syn_config=self._sintese):
            yield Trecho(
                pcm=chunk.audio_int16_bytes,
                taxa=chunk.sample_rate,
                canais=chunk.sample_channels,
            )


class VozKokoro(Voz):
    """Kokoro-82M pela placa de vídeo (out/2026, escolha do Léo: `pm_alex`).

    Mais natural que o Piper e, na GPU, mais rápido: 0,27 s para 7,4 s de fala
    (no processador eram 4,2 s). Fala frase por frase: a primeira já toca
    enquanto as outras são geradas.

    Precisa do `onnxruntime-gpu` 1.22 (CUDA 12, o mesmo do Whisper; o 1.31
    pede CUDA 13). Sem placa, roda no processador, mais devagar.
    """

    # Volume: o Kokoro sai ~8 dB abaixo do Piper. Sobe até um pouco ABAIXO do
    # que o Léo já ouvia (RMS 0,17 do faber) e nunca passa disso — o volume
    # já machucou o ouvido dele uma vez (HISTORIA, o volume que foi a 100).
    _RMS_ALVO = 0.14

    def __init__(self, cfg: ConfigTts, dir_vozes: Path) -> None:
        self.cfg = cfg
        modelo, vozes = dir_vozes / "kokoro-v1.0.onnx", dir_vozes / "voices-v1.0.bin"
        if not modelo.is_file() or not vozes.is_file():
            raise FileNotFoundError(
                f"Kokoro não encontrado em {dir_vozes}. Baixe kokoro-v1.0.onnx e "
                "voices-v1.0.bin de github.com/thewh1teagle/kokoro-onnx/releases "
                "(model-files-v1.0).")
        import onnxruntime as rt
        from kokoro_onnx import Kokoro

        inicio = time.monotonic()
        try:
            rt.preload_dlls()  # as bibliotecas CUDA dos pacotes nvidia-* do pip
        except Exception:
            pass
        sessao = rt.InferenceSession(
            str(modelo), providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        self.na_placa = "CUDAExecutionProvider" in sessao.get_providers()
        self._k = Kokoro.from_session(sessao, str(vozes))
        # Aquecimento: a primeira geração na placa custa ~0,9 s; as outras, 0,3.
        self._k.create("Oi.", voice=cfg.voz, speed=1.0, lang="pt-br")
        self.segundos_de_carga = time.monotonic() - inicio

    @property
    def nome(self) -> str:
        onde = "placa" if self.na_placa else "processador"
        efeito = f" + efeito {self.cfg.efeito}" if self.cfg.efeito else ""
        return f"kokoro {self.cfg.voz} ({onde}){efeito}"

    def sintetizar(self, texto: str) -> Iterator[Trecho]:
        import re

        import numpy as np

        frases = [f for f in re.split(r"(?<=[.!?…])\s+", texto.strip()) if f.strip()]
        # Tom: para engrossar sem ficar lento, o Kokoro fala mais rápido na
        # mesma proporção e o áudio é "esticado" de volta. Esticar baixa o tom
        # e os formantes juntos — a voz fica mais grave e encorpada, não só
        # mais baixa (pedido do Léo: a versão com efeito ficou "afeminada").
        fator = 2 ** (self.cfg.tom / 12)          # tom -3 → 0,84
        rapidez = min(2.0, (1.0 / max(0.5, self.cfg.velocidade)) / fator)
        for frase in frases:
            audio, taxa = self._k.create(frase, voice=self.cfg.voz, speed=rapidez,
                                         lang="pt-br")
            audio = np.asarray(audio, dtype=np.float32)
            if fator != 1.0:
                novo = int(len(audio) / fator)
                audio = np.interp(np.linspace(0, len(audio) - 1, novo),
                                  np.arange(len(audio)), audio).astype(np.float32)
            if self.cfg.efeito == "jarvis":
                audio = efeito_jarvis(audio, taxa)
            elif self.cfg.efeito == "suave":
                audio = efeito_suave(audio, taxa)
            rms = float(np.sqrt(np.mean(audio ** 2))) or 1.0
            ganho = min(self._RMS_ALVO / rms, 0.95 / max(float(np.max(np.abs(audio))), 1e-6))
            pcm = np.clip(audio * ganho, -1.0, 1.0)
            # Um respiro curto entre frases, como quem fala.
            pcm = np.concatenate([pcm, np.zeros(int(taxa * 0.12), dtype=np.float32)])
            yield Trecho(pcm=(pcm * 32767).astype(np.int16).tobytes(), taxa=taxa, canais=1)


def efeito_jarvis(audio, taxa: int):
    """Voz de "IA no capacete": ecos curtos e próximos (sala metálica pequena)
    e um reforço leve nos graves. Sutil de propósito: tem que continuar
    natural, só com o ar de máquina do filme.

    A primeira versão realçava os agudos e deixou a voz fina demais; agora é o
    contrário: um passa-baixa simples somado ao sinal dá corpo."""
    import numpy as np

    saida = np.concatenate([audio, np.zeros(int(taxa * 0.12), dtype=np.float32)])
    for atraso_ms, ganho in ((11, 0.30), (23, 0.20), (37, 0.12), (53, 0.07)):
        d = int(taxa * atraso_ms / 1000)
        saida[d:d + len(audio)] += ganho * audio
    # Graves: média móvel de ~2 ms (passa-baixa) somada ao sinal.
    janela = max(1, int(taxa * 0.002))
    graves = np.convolve(saida, np.ones(janela, dtype=np.float32) / janela, mode="same")
    return saida + 0.45 * graves


def efeito_suave(audio, taxa: int):
    """Só corpo nos graves, sem os ecos do "jarvis" (out/2026, pedido do Léo:
    "menos robotizada"). Os ecos curtos somados à voz são um filtro pente:
    é deles o som metálico de máquina."""
    import numpy as np

    janela = max(1, int(taxa * 0.002))
    graves = np.convolve(audio, np.ones(janela, dtype=np.float32) / janela, mode="same")
    return audio + 0.30 * graves


def falar(
    voz: Voz,
    texto: str,
    *,
    dispositivo: int | None = None,
    ao_comecar=None,
    parar=None,
) -> TemposDaFala:
    """Sintetiza e toca, medindo síntese e reprodução separadamente.

    Os trechos vão para a saída conforme saem do motor, em vez de esperar a
    frase inteira ficar pronta — isso derruba o tempo até o primeiro som.
    Para medir honesto apesar disso, cronometramos só as chamadas ao gerador
    (síntese pura); o `write`, que bloqueia enquanto a placa consome, conta
    como reprodução.
    """
    pedido_em = time.monotonic()
    gerador = voz.sintetizar(texto)
    # O volume da voz nos Ajustes da janela (0 a 100; 100 = o de sempre, o teto).
    from jarvis import ajustes
    volume = ajustes.ler()["volume_voz"] / 100

    primeiro_audio_s = 0.0
    sintese_total_s = 0.0
    amostras = 0
    taxa = 0
    stream: sd.RawOutputStream | None = None
    inicio_reproducao = 0.0

    parou = False
    try:
        while True:
            if parar is not None and parar():  # o botão Parar: corta no meio
                parou = True
                break
            marca = time.monotonic()
            try:
                trecho = next(gerador)
            except StopIteration:
                sintese_total_s += time.monotonic() - marca
                break
            sintese_total_s += time.monotonic() - marca

            if stream is None:
                primeiro_audio_s = time.monotonic() - pedido_em
                taxa = trecho.taxa
                from . import som
                stream = sd.RawOutputStream(
                    samplerate=trecho.taxa,
                    channels=trecho.canais,
                    dtype="int16",
                    device=som.aparelho(dispositivo, entrada=False),
                )
                stream.start()
                inicio_reproducao = time.monotonic()
                # O texto aparece na janela junto com a voz, não antes dela.
                if ao_comecar is not None:
                    ao_comecar()
                    ao_comecar = None

            pcm = trecho.pcm
            if volume < 1:
                import numpy as np
                pcm = (np.frombuffer(pcm, dtype=np.int16) * volume).astype(np.int16).tobytes()
            # Em fatias de 0,1 s: o Parar corta no meio da frase.
            passo = int(trecho.taxa * 0.1) * 2 * trecho.canais
            for i in range(0, len(pcm), passo):
                if parar is not None and parar():
                    parou = True
                    break
                stream.write(pcm[i:i + passo])
            if parou:
                break
            amostras += len(trecho.pcm) // (2 * trecho.canais)

        if stream is None:  # texto vazio ou sem áudio
            if ao_comecar is not None:
                ao_comecar()
            return TemposDaFala(0.0, sintese_total_s, 0.0, 0.0)

        # O write só bloqueia até caber no buffer: ao sair do laço ainda há
        # áudio na fila da placa. Esperar o resto evita cortar o fim da frase
        # e, principalmente, evita reabrir o microfone com o Jarvis ainda
        # falando — o que realimentaria o VAD.
        duracao_audio_s = amostras / taxa
        restante = duracao_audio_s - (time.monotonic() - inicio_reproducao)
        while restante > 0 and not parou:
            time.sleep(min(restante, 0.1))
            parou = parar is not None and parar()
            restante = duracao_audio_s - (time.monotonic() - inicio_reproducao)

        return TemposDaFala(
            primeiro_audio_s=primeiro_audio_s,
            sintese_total_s=sintese_total_s,
            reproducao_s=time.monotonic() - inicio_reproducao,
            duracao_audio_s=duracao_audio_s,
        )
    finally:
        if stream is not None:
            stream.abort() if parou else stream.stop()
            stream.close()


class Locutor:
    """A fala em fluxo (25/10/2026): o texto chega aos pedaços, enquanto o
    Claude ainda escreve, e cada pedaço sai assim que a voz fica pronta; o
    próximo é gerado enquanto o anterior toca.

    Duas threads: uma gera a voz; a outra toca no PC (`no_pc`) ou, para o
    celular, só passa os trechos adiante (ele toca lá). Quem usa recolhe os
    avisos na thread de áudio, com `avisos()`:

        ("comecou", marca)   o pedaço com essa marca começou a soar
        ("trecho", Trecho)   só fora do PC: o áudio para mandar ao celular
        ("acabou", None)     tudo dito (ou cancelado): o locutor terminou
    """

    _FIM = object()
    _SEM_MARCA = object()  # trecho do meio de um pedaço

    def __init__(self, voz: Voz, *, no_pc: bool, dispositivo: int | None = None) -> None:
        import queue
        import threading

        self.voz = voz
        self.dispositivo = dispositivo
        self.fechado = False
        self.primeiro_som: float | None = None  # time.monotonic() do 1º som
        self.duracao_s = 0.0
        self._textos: queue.Queue = queue.Queue()
        self._trechos: queue.Queue = queue.Queue()
        self._avisos: queue.Queue = queue.Queue()
        self._parar = threading.Event()
        threading.Thread(target=self._gerar, args=(no_pc,), daemon=True, name="locutor-voz").start()
        if no_pc:
            threading.Thread(target=self._tocar, daemon=True, name="locutor-som").start()

    def dizer(self, texto: str, marca=None) -> None:
        """Enfileira um pedaço. Texto vazio não soa, mas o aviso "comecou" da
        marca sai na vez dele (serve de marcador)."""
        self._textos.put((texto, marca))

    def fechar(self) -> None:
        """Não vem mais nada: termina o que está na fila e acaba."""
        self.fechado = True
        self._textos.put(None)

    def cancelar(self) -> None:
        """Para já, no meio da frase."""
        self._parar.set()
        self.fechar()

    @property
    def cancelado(self) -> bool:
        return self._parar.is_set()

    def avisos(self) -> list[tuple]:
        import queue

        saida = []
        while True:
            try:
                saida.append(self._avisos.get_nowait())
            except queue.Empty:
                return saida

    def _gerar(self, no_pc: bool) -> None:
        destino = self._trechos if no_pc else self._avisos
        try:
            while not self._parar.is_set():
                item = self._textos.get()
                if item is None:
                    break
                texto, marca = item
                primeiro = True
                try:
                    for trecho in self.voz.sintetizar(texto) if texto.strip() else ():
                        if self._parar.is_set():
                            break
                        if no_pc:
                            self._trechos.put((trecho, marca if primeiro else self._SEM_MARCA))
                        else:
                            if primeiro:
                                self._avisos.put(("comecou", marca))
                                if self.primeiro_som is None:
                                    self.primeiro_som = time.monotonic()
                            self.duracao_s += len(trecho.pcm) / 2 / trecho.taxa
                            self._avisos.put(("trecho", trecho))
                        primeiro = False
                except Exception as e:  # a voz caiu: o texto segue na tela, o resto também
                    print(f"  locutor: a voz falhou ({e.__class__.__name__}: {e})", flush=True)
                if primeiro:  # não soou nada: o marcador sai mesmo assim
                    destino.put((None, marca) if no_pc else ("comecou", marca))
        finally:
            if no_pc:
                self._trechos.put(self._FIM)
            else:
                self._avisos.put(("acabou", None))

    def _tocar(self) -> None:
        import numpy as np

        from jarvis import ajustes
        volume = ajustes.ler()["volume_voz"] / 100
        stream: sd.RawOutputStream | None = None
        taxa = 0
        fim_do_som = 0.0  # quando o que já foi escrito na placa termina de soar
        try:
            while not self._parar.is_set():
                item = self._trechos.get()
                if item is self._FIM:
                    break
                trecho, marca = item
                if marca is not self._SEM_MARCA:
                    self._avisos.put(("comecou", marca))
                if trecho is None:
                    continue
                if stream is None or trecho.taxa != taxa:
                    # A voz reserva pode vir em outra taxa no meio da fala.
                    if stream is not None:
                        time.sleep(max(0.0, fim_do_som - time.monotonic()))
                        stream.stop()
                        stream.close()
                    taxa = trecho.taxa
                    from . import som
                    stream = sd.RawOutputStream(samplerate=taxa, channels=trecho.canais,
                                                dtype="int16", device=som.aparelho(self.dispositivo, entrada=False))
                    stream.start()
                if self.primeiro_som is None:
                    self.primeiro_som = time.monotonic()
                pcm = trecho.pcm
                if volume < 1:
                    pcm = (np.frombuffer(pcm, dtype=np.int16) * volume).astype(np.int16).tobytes()
                segundos = len(pcm) / 2 / trecho.canais / taxa
                self.duracao_s += segundos
                fim_do_som = max(time.monotonic(), fim_do_som) + segundos
                # Em fatias de 0,1 s: cancelar para no meio da frase.
                passo = int(taxa * 0.1) * 2 * trecho.canais
                for i in range(0, len(pcm), passo):
                    if self._parar.is_set():
                        break
                    stream.write(pcm[i:i + passo])
            if stream is not None and not self._parar.is_set():
                # O write volta antes de a placa terminar: espera o fim, para
                # não cortar a última sílaba nem reabrir o microfone cedo.
                time.sleep(max(0.0, fim_do_som - time.monotonic()))
        finally:
            if stream is not None:
                stream.abort() if self._parar.is_set() else stream.stop()
                stream.close()
            self._avisos.put(("acabou", None))


class VozF5(Voz):
    """A voz do JARVIS dublado (out/2026): F5-TTS treinado com 93 falas do
    filme, rodando no `servidor_voz.py` (outra venv, com PyTorch).

    Pede a fala pelo socket e toca frase por frase, conforme chegam: a
    primeira já toca enquanto o servidor gera a próxima (~1 s por frase
    curta, medido com 16 passos). **Se o servidor não responder, fala com a
    Kokoro** (`reserva`): o Jarvis nunca fica mudo por causa da voz.
    """

    _RMS_ALVO = VozKokoro._RMS_ALVO  # o mesmo volume da Kokoro, nunca acima

    def __init__(self, cfg: ConfigTts, reserva: Voz, espera_s: float = 45.0,
                 rotulo: str = "jarvis dublado") -> None:
        import os

        from . import canal

        self.rotulo = rotulo
        self.cfg = cfg
        self.reserva = reserva
        self.caminho = cfg.socket_f5 if os.path.isabs(cfg.socket_f5) else str(canal.pasta() / cfg.socket_f5)
        # O servidor sobe junto (jarvis.sh) e leva ~10 s carregando o modelo:
        # espera um pouco na partida em vez de começar já na reserva.
        inicio = time.monotonic()
        while not self._vivo() and time.monotonic() - inicio < espera_s:
            time.sleep(0.5)
        self.segundos_de_carga = reserva.segundos_de_carga + time.monotonic() - inicio

    def _vivo(self) -> bool:
        import json
        from . import canal

        try:
            with canal.conectar(self.caminho, timeout=2) as s:
                s.sendall(b'{"ping": true}\n')
                return json.loads(s.makefile("rb").readline() or b"{}").get("ok") is True
        except (OSError, ValueError):
            return False

    @property
    def nome(self) -> str:
        estado = "servidor no ar" if self._vivo() else "SERVIDOR FORA: falando com a reserva"
        return f"{self.rotulo} (F5, {estado}); reserva {self.reserva.nome}"

    def sintetizar(self, texto: str) -> Iterator[Trecho]:
        import json
        from . import canal

        import numpy as np

        entregou = False
        try:
            with canal.conectar(self.caminho, timeout=2) as s:
                s.settimeout(30)
                s.sendall(json.dumps({"texto": texto}, ensure_ascii=False).encode() + b"\n")
                arq = s.makefile("rb")
                while True:
                    cab = json.loads(arq.readline() or b'{"erro": "conexao fechada"}')
                    if cab.get("fim"):
                        return
                    if "erro" in cab:
                        raise OSError(cab["erro"])
                    bruto = arq.read(cab["n"])
                    audio = np.frombuffer(bruto, dtype=np.int16).astype(np.float32) / 32768
                    rms = float(np.sqrt(np.mean(audio ** 2))) or 1.0
                    ganho = min(self._RMS_ALVO / rms,
                                0.95 / max(float(np.max(np.abs(audio))), 1e-6))
                    pcm = np.clip(audio * ganho, -1.0, 1.0)
                    pcm = np.concatenate([pcm, np.zeros(int(cab["taxa"] * 0.12), dtype=np.float32)])
                    entregou = True
                    yield Trecho(pcm=(pcm * 32767).astype(np.int16).tobytes(),
                                 taxa=cab["taxa"], canais=1)
        except (OSError, ValueError, KeyError):
            if entregou:
                return  # caiu no meio: o que já foi dito fica, sem repetir
        yield from self.reserva.sintetizar(texto)


def _pedacos(texto: str) -> list[str]:
    """Frase por frase; frase longa quebra nas vírgulas. Cada pedaço é gerado
    enquanto o anterior toca: pedaço curto no começo = voz começa antes."""
    import re

    pedacos: list[str] = []
    for f in re.split(r"(?<=[.!?…])\s+", texto.strip()):
        if not f.strip():
            continue
        if len(f) <= 80:
            pedacos.append(f)
            continue
        atual = ""
        for parte in re.split(r"(?<=,)\s+", f):
            atual = f"{atual} {parte}".strip()
            if len(atual) >= 30:
                pedacos.append(atual)
                atual = ""
        if atual:
            if pedacos:
                pedacos[-1] = f"{pedacos[-1]} {atual}"
            else:
                pedacos.append(atual)
    return pedacos


class VozRVC(Voz):
    """A voz do JARVIS dublado, 2ª versão (out/2026): a Kokoro fala e o
    `servidor_rvc.py` troca o timbre pelo do JARVIS (RVC treinado com as
    mesmas 93 falas do filme). Substituiu a F5, cujo "s" estourava e abafava;
    o "s" aqui é o da Kokoro, limpo. O Léo aprovou de ouvido (20/10/2026).

    `entrada` é a Kokoro pura (sem efeito nem tom: o timbre vem do RVC);
    `reserva`, a Kokoro de sempre, para quando o servidor não responder.
    Frases curtas que se repetem ("Pois não?", "Tá bom.") ficam guardadas em
    disco já convertidas e saem na hora.
    """

    _RMS_ALVO = VozKokoro._RMS_ALVO  # o mesmo volume da Kokoro, nunca acima
    # Frases que o Jarvis fala sempre igual: convertidas logo na partida.
    FIXAS = ["Pois não?", "Tá bom.", "Parei.", "Pausei.", "Voltando.", "Próxima.", "Anterior.",
             "Pronto.", "Não consegui falar com o Claude agora. Tenta de novo?"]

    def __init__(self, cfg: ConfigTts, entrada: VozKokoro, reserva: Voz,
                 pasta_cache: Path, espera_s: float = 3.0) -> None:
        import os
        import threading

        from . import canal

        self.cfg = cfg
        self.entrada = entrada
        self.reserva = reserva
        self.caminho = cfg.socket_rvc if os.path.isabs(cfg.socket_rvc) else str(canal.pasta() / cfg.socket_rvc)
        self._pasta_base = pasta_cache
        self._guardadas: dict[str, bytes] = {}
        # O servidor sobe junto (jarvis.sh), mas leva ~50 s carregando: o
        # Jarvis não espera por ele. Até lá fala com a reserva, e a voz do
        # JARVIS entra sozinha quando o servidor responder.
        inicio = time.monotonic()
        self._rec = self._receita()
        while self._rec is None and time.monotonic() - inicio < espera_s:
            time.sleep(0.5)
            self._rec = self._receita()
        self.segundos_de_carga = entrada.segundos_de_carga + time.monotonic() - inicio
        threading.Thread(target=self._aquecer, daemon=True, name="voz-fixas").start()

    def _receita(self) -> str | None:
        """A receita do servidor (modelo e ajustes), ou None se ele não responde."""
        import json
        from . import canal

        try:
            with canal.conectar(self.caminho, timeout=2) as s:
                s.sendall(b'{"ping": true}\n')
                r = json.loads(s.makefile("rb").readline() or b"{}")
                return str(r.get("receita", "")) if r.get("ok") is True else None
        except (OSError, ValueError):
            return None

    def _arquivo(self, chave: str) -> Path | None:
        import hashlib

        if not self._rec:
            self._rec = self._receita()  # o servidor subiu depois do Jarvis
            if not self._rec:
                return None
        pasta = self._pasta_base / hashlib.sha1(
            f"{self._rec}|{self.cfg.voz}|{self.cfg.velocidade}".encode()).hexdigest()[:12]
        pasta.mkdir(parents=True, exist_ok=True)
        return pasta / (hashlib.sha1(chave.encode()).hexdigest() + ".pcm")

    def _aquecer(self) -> None:
        fim = time.monotonic() + 300
        while not self._rec and time.monotonic() < fim:
            time.sleep(2)
            self._rec = self._receita()
        for frase in self.FIXAS:
            try:
                for _ in self._converter_pedaco(frase):
                    pass
            except (OSError, ValueError, KeyError):
                return

    @property
    def nome(self) -> str:
        estado = "servidor no ar" if self._receita() is not None else \
            "SERVIDOR FORA: falando com a reserva"
        return f"jarvis dublado (Kokoro + RVC, {estado}); reserva {self.reserva.nome}"

    def _converter_pedaco(self, pedaco: str) -> Iterator[Trecho]:
        """Kokoro → servidor → volume igual ao da Kokoro. Levanta OSError se
        o servidor falhar."""
        import json
        from . import canal

        import numpy as np

        chave = " ".join(pedaco.lower().split())
        guardar = len(chave) <= 60
        if guardar:
            if chave not in self._guardadas:
                arq = self._arquivo(chave)
                if arq is not None and arq.is_file():
                    self._guardadas[chave] = arq.read_bytes()
            if chave in self._guardadas:
                yield Trecho(pcm=self._guardadas[chave], taxa=40000, canais=1)
                return
        if not self._rec:
            self._rec = self._receita()
            if not self._rec:  # fora do ar: nem gasta a Kokoro à toa
                raise OSError("servidor do timbre fora do ar")
        for trecho in self.entrada.sintetizar(pedaco):
            with canal.conectar(self.caminho, timeout=2) as s:
                s.settimeout(30)
                s.sendall(json.dumps({"taxa": trecho.taxa, "n": len(trecho.pcm)}).encode()
                          + b"\n" + trecho.pcm)
                arq_s = s.makefile("rb")
                cab = json.loads(arq_s.readline() or b'{"erro": "conexao fechada"}')
                if "erro" in cab:
                    raise OSError(cab["erro"])
                bruto = arq_s.read(cab["n"])
            audio = np.frombuffer(bruto, dtype=np.int16).astype(np.float32) / 32768
            rms = float(np.sqrt(np.mean(audio ** 2))) or 1.0
            ganho = min(self._RMS_ALVO / rms, 0.95 / max(float(np.max(np.abs(audio))), 1e-6))
            pcm = (np.clip(audio * ganho, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
            if guardar and len(self._guardadas) < 300:
                self._guardadas[chave] = pcm
                arq = self._arquivo(chave)
                if arq is not None:
                    arq.write_bytes(pcm)
            yield Trecho(pcm=pcm, taxa=cab["taxa"], canais=1)

    def sintetizar(self, texto: str) -> Iterator[Trecho]:
        pedacos = _pedacos(texto)
        for i, pedaco in enumerate(pedacos):
            try:
                yield from self._converter_pedaco(pedaco)
            except (OSError, ValueError, KeyError):
                self._rec = None  # pode voltar com outro modelo: pergunta de novo
                # Caiu: o que já foi dito fica, o resto sai na voz de reserva.
                yield from self.reserva.sintetizar(" ".join(pedacos[i:]))
                return


def criar_voz_friday(cfg: ConfigTts, socket: str, dir_vozes: Path) -> Voz:
    """A voz da Friday (25/10/2026): a Emilia dublada no servidor_friday.py
    (F5, mesmo protocolo do servidor_voz.py). Reserva: a Kokoro feminina
    (pf_dora), para nunca sair na voz do JARVIS nem ficar muda."""
    from dataclasses import replace

    reserva = VozKokoro(replace(cfg, voz="pf_dora", efeito="", tom=0.0), dir_vozes)
    # Espera curta: o servidor leva ~25 s carregando; até lá vale a reserva.
    return VozF5(replace(cfg, socket_f5=socket), reserva=reserva, espera_s=5.0, rotulo="friday (Emilia)")


def criar_voz(cfg: ConfigTts, dir_vozes: Path) -> Voz:
    if cfg.motor == "piper":
        return VozPiper(cfg, dir_vozes)
    if cfg.motor == "kokoro":
        return VozKokoro(cfg, dir_vozes)
    if cfg.motor == "f5":
        # A reserva é a Kokoro com as mesmas configurações de [tts].
        return VozF5(cfg, reserva=VozKokoro(cfg, dir_vozes))
    if cfg.motor == "rvc":
        # A entrada do RVC é a Kokoro pura (o tom e o corpo vêm do timbre do
        # JARVIS); a reserva, a Kokoro com as configurações de [tts].
        from dataclasses import replace

        reserva = VozKokoro(cfg, dir_vozes)
        entrada = VozKokoro(replace(cfg, efeito="", tom=0.0), dir_vozes)
        return VozRVC(cfg, entrada, reserva,
                      Path.home() / ".local/share/jarvis/voz-jarvis/cache-rvc")
    raise ValueError(f'motor de TTS desconhecido: "{cfg.motor}" '
                     '(existem "piper", "kokoro", "f5" e "rvc")')
