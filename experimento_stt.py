#!/usr/bin/env python3
"""Etapa 1 — EXPERIMENTO de transcrição em fala rápida.

O Léo relatou: falando rápido, "abre o loft" sai com as palavras coladas e
letras embaralhadas. O texto já chega errado no núcleo, então nem o casamento
aproximado tem chance — o problema é do Whisper, antes de tudo.

Duas hipóteses a testar, medindo em vez de opinar:

  1. `initial_prompt` com os nomes do `atalhos.toml`. Fala rápida é onde o
     modelo mais depende de contexto, e "loft" não é palavra em português.
  2. `beam_size`, hoje em 1. Foi escolhido na Etapa 0 para minimizar latência,
     quando latência era a pergunta em aberto. Hoje sobra folga.

**Fala sintetizada, não gravada.** O microfone do Léo tem mute físico e ele
está fora. O Piper gera as frases em várias velocidades (`length_scale` baixo =
mais rápido). Isso não reproduz a voz dele — mas a comparação **entre as
configurações** é válida, porque todas recebem exatamente o mesmo áudio. É
comparação relativa, e é disso que a decisão precisa.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import json
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from etapa0 import _reamostrar
from jarvis import config, tts
from jarvis.nucleo.atalhos import Tabela, normalizar
from jarvis.stt import Transcritor

RAIZ = Path(__file__).resolve().parent
REGUA = "─" * 78

# length_scale do Piper: 1.0 é o normal, menor é mais rápido.
VELOCIDADES = [("normal", 1.0), ("rápido", 0.70), ("muito rápido", 0.55)]

# Frases com os nomes dos atalhos — é onde o erro dói.
FRASES = [
    ("abre o loft", "loft"),
    ("abre o projeto loft", "projeto loft"),
    ("abre gravações", "gravações"),
    ("põe o loft na tela", "loft"),
    ("abre o projeto loft pra mim", "projeto loft"),
]


@dataclass(frozen=True)
class Config:
    rotulo: str
    vocabulario: bool
    beam: int


CONFIGS = [
    Config("beam 1, sem vocab  (ATUAL)", False, 1),
    Config("beam 1, com vocab", True, 1),
    Config("beam 3, sem vocab", False, 3),
    Config("beam 3, com vocab", True, 3),
    Config("beam 5, com vocab", True, 5),
]


def nome_sobreviveu(transcricao: str, alvo: str) -> bool:
    """O nome do atalho ainda é achável dentro do que foi transcrito?

    É esta a pergunta que importa: não interessa a frase inteira sair perfeita,
    interessa o nome chegar reconhecível ao casador. Varre janelas de palavras
    do mesmo tamanho do alvo e pega a melhor semelhança.
    """
    palavras = normalizar(transcricao).split()
    alvo_n = normalizar(alvo)
    largura = len(alvo_n.split())
    if not palavras:
        return False
    janelas = [
        " ".join(palavras[i : i + largura])
        for i in range(max(1, len(palavras) - largura + 1))
    ]
    return any(
        difflib.SequenceMatcher(None, alvo_n, j).ratio() >= 0.85 for j in janelas
    )


def semelhanca(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalizar(a), normalizar(b)).ratio()


def gerar_audios(cfg) -> list[tuple[str, str, str, np.ndarray]]:
    """Sintetiza cada frase em cada velocidade. Devolve áudio a 16kHz."""
    audios = []
    for rotulo_vel, escala in VELOCIDADES:
        voz_cfg = dataclasses.replace(cfg.tts, velocidade=escala)
        voz = tts.criar_voz(voz_cfg, cfg.dir_vozes)
        for frase, atalho in FRASES:
            trechos = list(voz.sintetizar(frase))
            pcm = b"".join(t.pcm for t in trechos)
            taxa = trechos[0].taxa
            a = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
            audios.append((rotulo_vel, frase, atalho, _reamostrar(a, taxa, 16000)))
    return audios


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Etapa 1 — experimento de STT")
    p.add_argument("--config", type=Path, default=None)
    args = p.parse_args(argv)

    cfg = config.carregar(args.config)
    tabela = Tabela.carregar(cfg.raiz / "atalhos.toml")
    nomes = [a.nome for a in tabela.atalhos]

    print(f"\nExperimento de transcrição — {cfg.stt.modelo}")
    print(f"  vocabulário     {', '.join(nomes)}  (do atalhos.toml)")
    print(f"  frases          {len(FRASES)} × {len(VELOCIDADES)} velocidades")
    print("\n  sintetizando o áudio de teste...", flush=True)
    audios = gerar_audios(cfg)
    duracoes = {}
    for vel, frase, _, a in audios:
        duracoes.setdefault(vel, []).append(len(a) / 16000)
    for vel, ds in duracoes.items():
        print(f"    {vel:<14} média {sum(ds)/len(ds):.2f}s por frase")

    print("\n  carregando Whisper...", flush=True)
    transcritor = Transcritor(cfg.stt)
    transcritor.aquecer()

    resultados = []
    for c in CONFIGS:
        # Mexe na config do transcritor já carregado: o modelo é o mesmo, só
        # os parâmetros de decodificação mudam. Recarregar seria desperdício.
        transcritor.cfg = dataclasses.replace(
            cfg.stt, beam_size=c.beam, usar_vocabulario=c.vocabulario
        )
        transcritor.usar_vocabulario(nomes)

        print(f"\n{REGUA}\n  {c.rotulo}\n{REGUA}")
        print(f"  {'velocidade':<14} {'transcrição':<44} {'nome':<5} {'s':>5}")
        print("  " + "-" * 74)

        por_vel: dict[str, list] = {}
        for vel, frase, atalho, audio in audios:
            t = transcritor.transcrever(audio)
            ok = nome_sobreviveu(t.texto, atalho)
            sim = semelhanca(t.texto, frase)
            por_vel.setdefault(vel, []).append((ok, sim, t.segundos))
            marca = "ok " if ok else "NAO"
            print(f"  {vel:<14} {t.texto[:44]:<44} {marca:<5} {t.segundos:>5.2f}")
            resultados.append(
                {
                    "config": c.rotulo,
                    "beam": c.beam,
                    "vocabulario": c.vocabulario,
                    "velocidade": vel,
                    "frase": frase,
                    "transcricao": t.texto,
                    "nome_sobreviveu": ok,
                    "semelhanca": round(sim, 3),
                    "segundos": round(t.segundos, 3),
                }
            )

        print("  " + "-" * 74)
        for vel, _ in VELOCIDADES:
            linhas = por_vel[vel]
            acertos = sum(1 for ok, _, _ in linhas if ok)
            print(
                f"  {vel:<14} nome sobreviveu {acertos}/{len(linhas)}"
                f"   semelhança média {sum(s for _, s, _ in linhas)/len(linhas):.0%}"
                f"   {sum(t for _, _, t in linhas)/len(linhas):.2f}s"
            )
        todos = [x for v in por_vel.values() for x in v]
        print(
            f"  {'TOTAL':<14} nome sobreviveu {sum(1 for ok,_,_ in todos if ok)}/{len(todos)}"
            f"   semelhança média {sum(s for _,s,_ in todos)/len(todos):.0%}"
            f"   {sum(t for _,_,t in todos)/len(todos):.2f}s"
        )

    destino = RAIZ / "medicoes"
    destino.mkdir(exist_ok=True)
    caminho = destino / f"etapa1-stt-{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    with caminho.open("w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "tipo": "sessao",
                    "momento": datetime.now().isoformat(timespec="seconds"),
                    "modelo": cfg.stt.modelo,
                    "compute_type": cfg.stt.compute_type,
                    "vocabulario": nomes,
                    "aviso": "áudio sintetizado no Piper, não gravado do Léo",
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        for r in resultados:
            f.write(json.dumps({"tipo": "medicao", **r}, ensure_ascii=False) + "\n")

    print(f"\n{REGUA}\n  medições em {caminho.relative_to(RAIZ)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
