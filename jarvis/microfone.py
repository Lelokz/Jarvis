"""Captura contínua do microfone: 16kHz, mono, int16.

O bloco é de 512 amostras (32ms) porque é exatamente o chunk que o Silero VAD
consome. Alinhar os dois significa que cada bloco que sai do PortAudio vira
uma decisão do VAD direto, sem remontar buffer no meio do caminho.

Aqui também mora o portão anti-eco. A saída padrão desta máquina são as caixas
da placa-mãe, não o headset: sem fechar a captura enquanto o Jarvis fala, o
microfone pega a própria resposta, o VAD dispara, o Whisper transcreve e ele
responde a si mesmo em laço. Enquanto o portão está fechado nada entra na
fila, e na reabertura o que sobrou é descartado.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass

import sounddevice as sd


@dataclass(frozen=True)
class Dispositivo:
    indice: int
    nome: str
    canais_entrada: int
    canais_saida: int
    taxa_padrao: float
    padrao_entrada: bool
    padrao_saida: bool


def listar_dispositivos() -> list[Dispositivo]:
    try:
        entrada_padrao, saida_padrao = sd.default.device
    except (TypeError, ValueError):
        entrada_padrao = saida_padrao = -1

    return [
        Dispositivo(
            indice=i,
            nome=d["name"],
            canais_entrada=d["max_input_channels"],
            canais_saida=d["max_output_channels"],
            taxa_padrao=d["default_samplerate"],
            padrao_entrada=(i == entrada_padrao),
            padrao_saida=(i == saida_padrao),
        )
        for i, d in enumerate(sd.query_devices())
    ]


def resolver(trecho: str, *, entrada: bool) -> int | None:
    """Casa um trecho do nome com um dispositivo. "" = padrão do sistema."""
    if not trecho.strip():
        return None

    alvo = trecho.strip().lower()
    candidatos = [
        d
        for d in listar_dispositivos()
        if (d.canais_entrada if entrada else d.canais_saida) > 0
        and alvo in d.nome.lower()
    ]
    if not candidatos:
        tipo = "entrada" if entrada else "saída"
        disponiveis = "\n".join(
            f"    [{d.indice}] {d.nome}"
            for d in listar_dispositivos()
            if (d.canais_entrada if entrada else d.canais_saida) > 0
        )
        raise ValueError(
            f'Nenhum dispositivo de {tipo} casa com "{trecho}".\n'
            f"  Disponíveis:\n{disponiveis}"
        )
    return candidatos[0].indice


def nome_do_dispositivo(indice: int | None, *, entrada: bool) -> str:
    if indice is None:
        try:
            padrao = sd.default.device[0 if entrada else 1]
            return f"{sd.query_devices(padrao)['name']} (padrão do sistema)"
        except Exception:
            return "padrão do sistema"
    return sd.query_devices(indice)["name"]


class Microfone:
    """Fluxo de entrada com fila e portão anti-eco. Use como context manager."""

    def __init__(
        self,
        *,
        taxa: int,
        amostras_por_bloco: int,
        dispositivo: int | None = None,
    ) -> None:
        self.taxa = taxa
        self.amostras_por_bloco = amostras_por_bloco
        self.dispositivo = dispositivo

        self._fila: queue.Queue[bytes] = queue.Queue()
        self._portao_aberto = threading.Event()
        self._portao_aberto.set()
        self._stream: sd.RawInputStream | None = None
        self.estouros = 0

    # -- ciclo de vida -----------------------------------------------------

    def __enter__(self) -> Microfone:
        self._stream = sd.RawInputStream(
            samplerate=self.taxa,
            blocksize=self.amostras_por_bloco,
            device=self.dispositivo,
            channels=1,
            dtype="int16",
            callback=self._callback,
        )
        self._stream.start()
        return self

    def __exit__(self, *_) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    # -- captura -----------------------------------------------------------

    def _callback(self, indata, frames, tempo, status) -> None:
        if status.input_overflow:
            # Bloco perdido pelo PortAudio. Contamos e seguimos: derrubar o
            # programa por causa de um hiccup de áudio seria pior.
            self.estouros += 1
        if self._portao_aberto.is_set():
            self._fila.put(bytes(indata))

    def ler_bloco(self, timeout: float = 0.5) -> bytes | None:
        try:
            return self._fila.get(timeout=timeout)
        except queue.Empty:
            return None

    # -- portão anti-eco ---------------------------------------------------

    def fechar_portao(self) -> None:
        self._portao_aberto.clear()

    def abrir_portao(self) -> None:
        self._drenar()
        self._portao_aberto.set()

    def _drenar(self) -> None:
        while True:
            try:
                self._fila.get_nowait()
            except queue.Empty:
                return
