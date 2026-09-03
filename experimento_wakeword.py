#!/usr/bin/env python3
"""Etapa 0.5 — EXPERIMENTO de wake word. Não é implementação.

Existe para responder uma pergunta, e só ela:

    o modelo `hey_jarvis` pré-treinado do openWakeWord dispara com a voz do
    Léo, falando português com sotaque brasileiro?

O modelo foi treinado em inglês e a documentação diz que só há suporte a
modelos em inglês. O Léo fala "Járvis", não "Djárvis". Ninguém sabe se
reconhece — por isso medimos antes de construir qualquer coisa em cima.

Este script é deliberadamente isolado: não importa nada do `etapa0.py`, não
faz STT, não faz TTS, não toca no ciclo aprovado na Etapa 0. A única coisa
que reaproveita é `jarvis/microfone.py`, que já é captura de microfone
depurada.

Instalação: ver requirements-wakeword.txt (NÃO é um `pip install -r` direto).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import wave
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from jarvis import microfone, wakeword

RAIZ = Path(__file__).resolve().parent
DIR_MODELOS = RAIZ / "modelos-wakeword"
DIR_LOGS = RAIZ / "logs"

TAXA = 16000
# 1280 amostras = 80ms. É o frame do openWakeWord. Note que o VAD da Etapa 0
# usa 512 (32ms): os números não são múltiplos, e é por isso que este
# experimento não compartilha o fluxo de áudio com o loop principal.
AMOSTRAS_POR_BLOCO = 1280
DURACAO_BLOCO_S = AMOSTRAS_POR_BLOCO / TAXA

PRE_ROLL_S = 2.0
POS_ROLL_S = 1.0
LARGURA_BARRA = 40
REGUA = "─" * 58

# Limiares simulados no resumo do fim da sessão.
LIMIARES_SIMULADOS = (0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)


def num(x: float) -> str:
    """Limiar legível: 0.5 vira "0.5", 0.0002 continua "0.0002"."""
    return f"{x:g}"


def _kv(rotulo: str, valor: object) -> str:
    """Rótulo à esquerda, valor encostado na régua — some qual for o rótulo."""
    texto = str(valor)
    folga = len(REGUA) - 2 - len(rotulo) - len(texto)
    return "  " + rotulo + " " * max(1, folga) + texto


# ---------------------------------------------------------------------------
# registro
# ---------------------------------------------------------------------------


@dataclass
class Gravador:
    """jsonl das medições + wav de cada disparo.

    Escrito à parte do `jarvis/registro.py` de propósito: aquele é acoplado a
    `Segmento` e `Tempos`, que são da cadeia da Etapa 0 e têm forma errada
    para eventos de wake word. Refatorá-lo mexeria em código já aprovado e em
    produção por uma economia de umas 20 linhas. Se o wake word passar no
    teste e virar integração, aí vale unificar os dois.
    """

    caminho_jsonl: Path
    dir_audio: Path | None

    @classmethod
    def criar(cls, salvar_audio: bool) -> Gravador:
        carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
        DIR_LOGS.mkdir(parents=True, exist_ok=True)
        dir_audio = None
        if salvar_audio:
            dir_audio = DIR_LOGS / "audio-wake"
            dir_audio.mkdir(parents=True, exist_ok=True)
        return cls(DIR_LOGS / f"wake-{carimbo}.jsonl", dir_audio)

    def escrever(self, linha: dict) -> None:
        with self.caminho_jsonl.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")

    def salvar_wav(self, identificador: str, pcm: bytes) -> str | None:
        if self.dir_audio is None:
            return None
        caminho = self.dir_audio / f"{identificador}.wav"
        with wave.open(str(caminho), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(TAXA)
            w.writeframes(pcm)
        return caminho.name


# ---------------------------------------------------------------------------
# medições
# ---------------------------------------------------------------------------


@dataclass
class Sessao:
    """Guarda todo frame acima do piso, para o resumo poder simular limiares."""

    piso: float
    limiar: float
    refratario_s: float
    scores: list[float] = field(default_factory=list)
    momentos: list[float] = field(default_factory=list)
    frames_totais: int = 0
    disparos: int = 0
    inicio: float = field(default_factory=time.monotonic)

    def registrar(self, score: float, momento: float) -> None:
        self.frames_totais += 1
        if score >= self.piso:
            self.scores.append(score)
            self.momentos.append(momento)

    def simular(self, limiar: float) -> int:
        """Quantos disparos teriam ocorrido com outro limiar.

        Reaplica a mesma janela refratária sobre os frames gravados, para o
        número ser comparável ao contador ao vivo. Só vale para limiares >=
        piso, porque abaixo disso não guardamos os frames.
        """
        eventos = 0
        ultimo = -1e9
        for score, momento in zip(self.scores, self.momentos):
            if score >= limiar and momento - ultimo >= self.refratario_s:
                eventos += 1
                ultimo = momento
        return eventos

    def resumo(self) -> str:
        duracao = time.monotonic() - self.inicio
        minutos, segundos = divmod(int(duracao), 60)

        linhas = [
            "",
            REGUA,
            f"  RESUMO — {minutos} min {segundos:02d} s de escuta",
            REGUA,
            _kv(f"disparos (≥ {num(self.limiar)})", self.disparos),
            _kv(f"frames acima do piso ({num(self.piso)})", len(self.scores)),
            _kv("frames totais", self.frames_totais),
        ]

        if not self.scores:
            linhas += [
                REGUA,
                f"  Nenhum frame passou do piso de {num(self.piso)}.",
                "  Ou ninguém falou, ou o modelo não reagiu de jeito nenhum.",
                REGUA,
                "",
            ]
            return "\n".join(linhas)

        ordenados = sorted(self.scores)
        linhas += [
            REGUA,
            f"  distribuição dos scores ≥ {num(self.piso)}",
            f"    mín    {ordenados[0]:.2f}",
            f"    p50    {statistics.median(ordenados):.2f}",
            f"    p90    {ordenados[int(len(ordenados) * 0.9) - 1]:.2f}",
            f"    máx    {ordenados[-1]:.2f}",
            REGUA,
            "  quantos disparos sobrariam por limiar:",
        ]
        pares = [(lim, self.simular(lim)) for lim in LIMIARES_SIMULADOS]
        metade = (len(pares) + 1) // 2
        for i in range(metade):
            esq = f"    {pares[i][0]:.2f} → {pares[i][1]:>4}"
            dir_ = ""
            if i + metade < len(pares):
                p = pares[i + metade]
                dir_ = f"        {p[0]:.2f} → {p[1]:>4}"
            linhas.append(esq + dir_)
        linhas += [REGUA, ""]
        return "\n".join(linhas)


# ---------------------------------------------------------------------------


def carregar_modelo(caminho_modelo: Path):
    """Carrega o modelo pelos mesmos parâmetros que o assistente usa.

    A implementação mora em `jarvis/wakeword.py` desde a Etapa 0.6. Ter uma
    cópia aqui e outra lá seria o jeito de os dois divergirem em silêncio — e
    no dia em que divergissem, a medição desta etapa deixaria de valer para o
    que roda de verdade.
    """
    return wakeword.carregar_modelo(caminho_modelo, DIR_MODELOS)


def checar_nivel(mic: microfone.Microfone, segundos: float = 1.0) -> None:
    """Mede o nível do microfone antes de começar, e avisa se estiver mudo.

    O Fifine tem botão de mute no próprio corpo, e o Léo costuma deixá-lo
    mutado quando sai. Esse botão é invisível para o sistema: o PipeWire
    reporta `Mudo: não` e o volume em 71% enquanto o hardware entrega silêncio
    digital (RMS 1 de 32767). Não há como detectar isso pela configuração —
    só medindo o sinal.

    Sem esta checagem, um experimento rodado com o mute ligado dá zero
    disparos, e a conclusão errada seria "o modelo não entende meu sotaque"
    quando o microfone simplesmente não captou nada. Um segundo de medição
    evita jogar fora uma tarde de teste.
    """
    picos = []
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        bloco = mic.ler_bloco(timeout=0.3)
        if bloco is not None:
            picos.append(np.abs(np.frombuffer(bloco, dtype=np.int16)).max())

    if not picos:
        print("  nível do mic     SEM BLOCOS — o microfone não entregou áudio\n")
        return

    pico = int(max(picos))
    if pico < 50:
        print(f"  nível do mic     PICO {pico}/32767 — praticamente silêncio")
        print("\n  ATENÇÃO: este microfone não está captando nada.")
        print("  Rodar assim dá zero disparos por falha de captura, não do modelo.")
        print("  Veja as opções com --listar-dispositivos e escolha outra com")
        print("  --dispositivo <trecho do nome>.\n")
    else:
        print(f"  nível do mic     pico {pico}/32767 no último segundo — captando\n")


def barra(score: float, disparou: bool) -> str:
    cheias = int(round(score * LARGURA_BARRA))
    marca = "#" if disparou else "·"
    return (marca * cheias).ljust(LARGURA_BARRA)


def escutar(args: argparse.Namespace) -> int:
    caminho_modelo = DIR_MODELOS / "hey_jarvis_v0.1.onnx"
    if not caminho_modelo.is_file():
        print(
            f"\nModelo não encontrado: {caminho_modelo}\n"
            "  Baixe com:\n"
            "    ./.venv/bin/python -c \"import openwakeword.utils as u; "
            "u.download_models(model_names=['hey_jarvis'], "
            "target_directory='modelos-wakeword')\"\n",
            file=sys.stderr,
        )
        return 1

    try:
        indice = microfone.resolver(args.dispositivo, entrada=True)
    except ValueError as e:
        print(f"\n{e}\n", file=sys.stderr)
        return 1

    oww = carregar_modelo(caminho_modelo)
    rotulo = next(iter(oww.models.keys()))
    gravador = Gravador.criar(not args.sem_audio)
    sessao = Sessao(piso=args.piso, limiar=args.limiar, refratario_s=args.refratario)

    print("\nExperimento wake word — hey_jarvis (openWakeWord 0.6.0, onnx)")
    print(f"  microfone        {microfone.nome_do_dispositivo(indice, entrada=True)}")
    print(f"  modelo           {caminho_modelo.relative_to(RAIZ)}")
    print("  VAD interno      desligado (vad_threshold=0)")
    print(f"  piso de registro {num(args.piso)}")
    print(f"  limiar           {num(args.limiar)}")
    print(f"  refratário       {args.refratario:.1f} s")
    print(f"  log              {gravador.caminho_jsonl.relative_to(RAIZ)}")
    if gravador.dir_audio:
        print(f"  áudio            {gravador.dir_audio.relative_to(RAIZ)}/")

    gravador.escrever(
        {
            "tipo": "sessao",
            "momento": datetime.now().isoformat(timespec="seconds"),
            "modelo": caminho_modelo.name,
            "rotulo": rotulo,
            "framework": "onnx",
            "vad_threshold": 0,
            "piso": args.piso,
            "limiar": args.limiar,
            "refratario_s": args.refratario,
            "dispositivo": microfone.nome_do_dispositivo(indice, entrada=True),
        }
    )

    print()

    # Buffer circular: o modelo só pontua alto DEPOIS de ouvir a palavra
    # inteira, então sem guardar o áudio anterior o .wav começaria depois do
    # "ei Jarvis" e não serviria para auditar nada.
    pre_roll: deque[bytes] = deque(maxlen=int(PRE_ROLL_S / DURACAO_BLOCO_S))
    blocos_pos = int(POS_ROLL_S / DURACAO_BLOCO_S)
    pendente: list[bytes] | None = None
    faltam = 0
    id_pendente = ""
    ultimo_disparo = -1e9

    mic: microfone.Microfone | None = None
    try:
        with microfone.Microfone(
            taxa=TAXA,
            amostras_por_bloco=AMOSTRAS_POR_BLOCO,
            dispositivo=indice,
        ) as mic:
            checar_nivel(mic)
            print('rodando. fale "ei Jarvis". (ctrl+c encerra e mostra o resumo)\n')
            # O segundo gasto na checagem não conta como tempo de escuta.
            sessao.inicio = time.monotonic()
            while True:
                bloco = mic.ler_bloco()
                if bloco is None:
                    continue

                pre_roll.append(bloco)
                agora = time.monotonic()
                score = float(
                    oww.predict(np.frombuffer(bloco, dtype=np.int16))[rotulo]
                )
                sessao.registrar(score, agora)

                # Fecha a captura de um disparo anterior, se houver.
                if pendente is not None:
                    pendente.append(bloco)
                    faltam -= 1
                    if faltam <= 0:
                        gravador.salvar_wav(id_pendente, b"".join(pendente))
                        pendente = None

                if score < args.piso:
                    continue

                # Refratário aplicado só na CONTAGEM. O score em si nunca é
                # tocado: o debounce_time da própria lib zera o valor
                # (predictions[mdl] = 0.0), o que corromperia justamente a
                # distribuição que queremos medir.
                disparou = (
                    score >= args.limiar
                    and agora - ultimo_disparo >= args.refratario
                )

                identificador = ""
                if disparou:
                    ultimo_disparo = agora
                    sessao.disparos += 1
                    momento = datetime.now()
                    identificador = momento.strftime("%Y%m%d-%H%M%S-") + (
                        f"{momento.microsecond // 1000:03d}"
                    )
                    if gravador.dir_audio and pendente is None:
                        pendente = list(pre_roll)
                        faltam = blocos_pos
                        id_pendente = identificador

                marca = ">" if disparou else " "
                sufixo = f"   [disparo #{sessao.disparos}]" if disparou else ""
                print(
                    f"{marca} {score:.2f}  {barra(score, disparou)}  "
                    f"{datetime.now():%H:%M:%S}{sufixo}"
                )

                gravador.escrever(
                    {
                        "tipo": "frame",
                        "momento": datetime.now().isoformat(timespec="milliseconds"),
                        "score": round(score, 5),
                        "disparo": disparou,
                        "audio": f"{identificador}.wav" if disparou else None,
                    }
                )

    except KeyboardInterrupt:
        print()
    finally:
        # Não perde o áudio de um disparo interrompido no meio da captura.
        if pendente is not None:
            gravador.salvar_wav(id_pendente, b"".join(pendente))
        print(sessao.resumo())
        if mic is not None and mic.estouros:
            print(f"  blocos perdidos pelo PortAudio: {mic.estouros}")
        print(f"  medições em {gravador.caminho_jsonl}\n")
    return 0


def listar() -> int:
    print("\nENTRADAS (microfone)")
    for d in microfone.listar_dispositivos():
        if d.canais_entrada:
            marca = " ← padrão do sistema" if d.padrao_entrada else ""
            print(f"  [{d.indice:>2}] {d.nome}{marca}")
    print("\nUse --dispositivo com um trecho do nome para fixar um deles.\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Experimento: o hey_jarvis pronto dispara com a voz do Léo?"
    )
    p.add_argument("--limiar", type=float, default=0.5, help="score que conta como disparo (padrão 0.5)")
    p.add_argument("--piso", type=float, default=0.1, help="score mínimo para registrar (padrão 0.1)")
    p.add_argument("--refratario", type=float, default=1.5, help="segundos entre disparos (padrão 1.5)")
    p.add_argument("--dispositivo", default="", help="trecho do nome do microfone")
    p.add_argument("--sem-audio", action="store_true", help="não gravar os .wav")
    p.add_argument("--listar-dispositivos", action="store_true")
    args = p.parse_args(argv)

    if args.listar_dispositivos:
        return listar()
    if not 0 < args.piso <= args.limiar <= 1:
        print("\nExige-se 0 < piso <= limiar <= 1.\n", file=sys.stderr)
        return 1
    return escutar(args)


if __name__ == "__main__":
    sys.exit(main())
