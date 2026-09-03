#!/usr/bin/env python3
"""Verifica a linha núcleo/cliente do ESCOPO §4.

O núcleo não pode saber o que é microfone, voz ou wake word. Essa regra é fácil
de escrever e fácil de furar sem querer — um import inocente num arquivo novo e
a separação some, só reaparecendo no dia em que alguém tentar escrever o
cliente de celular e descobrir que o núcleo puxa `sounddevice`.

Então ela é checada, não prometida. Roda em segundos e serve de guarda para as
próximas etapas.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
NUCLEO = RAIZ / "jarvis" / "nucleo"

# O que o núcleo não pode conhecer, de jeito nenhum.
PROIBIDOS = {
    "sounddevice",
    "microfone",
    "vad",
    "stt",
    "tts",
    "wakeword",
    "assistente",
    "etapa0",
}


def importados(caminho: Path) -> set[str]:
    """Nomes de módulo importados, incluindo os relativos (`from ..vad import`)."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    nomes: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes.update(a.name.split(".")[0] for a in no.names)
        elif isinstance(no, ast.ImportFrom):
            if no.module:
                nomes.update(no.module.split("."))
            # `from . import vad` — o nome importado é o módulo
            nomes.update(a.name for a in no.names)
    return nomes


def main() -> int:
    if not NUCLEO.is_dir():
        print(f"jarvis/nucleo/ não existe em {NUCLEO}", file=sys.stderr)
        return 1

    arquivos = sorted(NUCLEO.rglob("*.py"))
    violacoes: list[tuple[Path, set[str]]] = []
    for arquivo in arquivos:
        ruins = importados(arquivo) & PROIBIDOS
        if ruins:
            violacoes.append((arquivo, ruins))

    print(f"\nLinha núcleo/cliente — {len(arquivos)} arquivo(s) em jarvis/nucleo/")
    for arquivo in arquivos:
        print(f"  {arquivo.relative_to(RAIZ)}")

    if violacoes:
        print("\n  FUROU A LINHA:")
        for arquivo, ruins in violacoes:
            print(f"    {arquivo.relative_to(RAIZ)} importa {', '.join(sorted(ruins))}")
        print(
            "\n  O núcleo tem que funcionar sem microfone nenhum. Se precisa de\n"
            "  áudio, o lugar é o cliente (assistente.py).\n"
        )
        return 1

    print("\n  OK — o núcleo não conhece áudio.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
