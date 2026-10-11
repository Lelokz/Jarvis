"""O terminal do Ciclo, linha a linha, com peças falsas.

A passada 2 da Etapa 6 transformou cada print do `Ciclo` num evento com o
terminal como assinante. A promessa era que o terminal ficasse IDÊNTICO — e
promessa sobre saída se prova comparando a saída. Este roteiro roda o `Ciclo`
de verdade, sem microfone, sem som, sem GPU e sem LLM, e passa por todas as
linhas que ele imprime.

    python3 testes/terminal_identico.py            # confere
    python3 testes/terminal_identico.py --gravar   # imprime o bloco novo

**As linhas esperadas moram aqui dentro**, e não num arquivo gravado à parte,
para o teste não depender de uma sobra de rascunho. São as 15 linhas medidas
ANTES da refatoração, em 14/set/2026.

Normalizados: o relógio, e os dois números que são medidos de verdade — o
tempo do núcleo e a latência, que depende dele. `stt` e `tts` são fixados
pelas peças falsas e continuam conferidos, letra por letra.

**Depende do config.toml**: nome da persona, saudação e a janela de 30 s
aparecem no texto. Mudou um deles, este teste acusa — e a saída dele diz qual.
"""
import contextlib
import io
import re
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import numpy as np

import assistente
from jarvis import config, wakeword
from jarvis.nucleo.nucleo import Resposta
from jarvis.registro import Registrador
from jarvis.stt import Transcricao
from jarvis.tts import Voz
from jarvis.vad import MotivoDoFim, Segmento


class VozMuda(Voz):
    """Não sintetiza nada: o `tts.falar` volta sem abrir a placa de som."""

    nome = "muda"

    def sintetizar(self, texto):
        return iter(())


class VadRoteirizado:
    amostras_por_bloco = 512
    descartados_curtos = 0

    def __init__(self):
        self.falando = False
        self.proximo = None

    def processar(self, bloco):
        seg, self.proximo = self.proximo, None
        return seg

    def reiniciar(self):
        self.falando = False


class WakeWordParado:
    ultimo_score = 0.0

    def processar(self, bloco):
        return False, None

    def reiniciar(self):
        pass

    def fechar_pendente(self):
        return None


class TranscritorRoteirizado:
    def __init__(self):
        self.texto = ""

    def transcrever(self, audio):
        return Transcricao(self.texto, 0.40, "pt", 0.99)


class NucleoRoteirizado:
    def __init__(self):
        self.resposta = Resposta("")

    def processar(self, texto):
        return self.resposta

    def aquecer(self):
        pass

    def reiniciar_conversa(self):
        pass


def segmento():
    return Segmento(
        audio=np.zeros(16000, dtype=np.float32), pcm=b"", taxa=16000,
        duracao_total_s=1.20, duracao_fala_s=0.90, espera_silencio_s=0.30,
        fechado_em=time.monotonic(), motivo=MotivoDoFim.SILENCIO,
    )


def montar(tmp: Path):
    cfg = config.carregar(RAIZ / "config.toml")
    vad, stt, nucleo = VadRoteirizado(), TranscritorRoteirizado(), NucleoRoteirizado()
    ciclo = assistente.Ciclo(
        cfg,
        detector_vad=vad,
        detector_ww=WakeWordParado(),
        transcritor=stt,
        voz=VozMuda(),
        nucleo=nucleo,
        registrador=Registrador(caminho_jsonl=tmp / "sessao.jsonl", dir_audio=None,
                                dir_audio_wake=None),
        portao=assistente._PortaoFalso(),
        dispositivo_saida=None,
    )
    return ciclo, vad, stt, nucleo


def roteiro_base(ciclo, vad, stt, nucleo):
    bloco = b"\x00" * 1024

    ciclo.acordar(0.87)

    vad.proximo = segmento()
    stt.texto = "abre o loft"
    nucleo.resposta = Resposta("Abri o Loft.", acao="abrir:loft")
    ciclo.passo(bloco)

    vad.proximo = segmento()
    stt.texto = "renomeia o relatório"
    nucleo.resposta = Resposta("Renomeio relatório para proposta. Pode?", perguntando=True)
    ciclo.passo(bloco)

    vad.proximo = segmento()
    stt.texto = ""
    ciclo.passo(bloco)

    ciclo._registrar_evento(wakeword.Evento(pico=0.41, disparou=False,
                                            pcm=b"\x00\x00" * 8, momento=0.0, frames=3))

    ciclo.prazo = 0.0
    ciclo.passo(bloco)
    ciclo.passo(bloco)  # dormindo: não imprime nada


ESPERADO = """\
  HH:MM:SS   ACORDOU           score 0.87
             jarvis: "Pois não?"
  HH:MM:SS   janela aberta     30 s
             você:   "abre o loft"
             jarvis: "Abri o Loft."
                     stt 0.40s · núcleo N.NNs · tts 0.00s · latência N.NNs
  HH:MM:SS   janela reiniciada 30 s
             você:   "renomeia o relatório"
             jarvis: "Renomeio relatório para proposta. Pode?"
                     stt 0.40s · núcleo N.NNs · tts 0.00s · latência N.NNs
  HH:MM:SS   janela reiniciada 30 s
  HH:MM:SS   não entendi       (nada transcrito — janela renovada)
  HH:MM:SS   janela reiniciada 30 s
  HH:MM:SS   quase-acerto      pico 0.41  (áudio gravado)
  HH:MM:SS   dormiu            30 s sem fala
"""


def normalizar(texto: str) -> str:
    texto = re.sub(r"\d{2}:\d{2}:\d{2}", "HH:MM:SS", texto)
    texto = re.sub(r"(núcleo|latência) \d+\.\d+s", r"\1 N.NNs", texto)
    return texto


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    saida = io.StringIO()
    with tempfile.TemporaryDirectory() as d:
        ciclo, vad, stt, nucleo = montar(Path(d))
        with contextlib.redirect_stdout(saida):
            roteiro_base(ciclo, vad, stt, nucleo)
    obtido = normalizar(saida.getvalue())

    if "--gravar" in argv:
        print(obtido, end="")
        return 0

    if obtido == ESPERADO:
        print(f"  PASSOU — o terminal do Ciclo está idêntico "
              f"({len(ESPERADO.splitlines())} linhas).")
        return 0

    print("  FALHOU — o terminal do Ciclo mudou:\n")
    esperadas, obtidas = ESPERADO.splitlines(), obtido.splitlines()
    for i in range(max(len(esperadas), len(obtidas))):
        e = esperadas[i] if i < len(esperadas) else "(nada)"
        o = obtidas[i] if i < len(obtidas) else "(nada)"
        if e != o:
            print(f"    linha {i + 1}\n      esperado: {e!r}\n      obtido:   {o!r}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
