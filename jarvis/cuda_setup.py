"""Pré-carrega as bibliotecas CUDA antes do primeiro import do ctranslate2.

Por que isto existe: o wheel do ctranslate2 tem 39MB e não embute CUDA. Ele
faz `dlopen` de `libcublas.so.12` e `libcudnn*.so.9` só na hora de rodar. Quem
instala torch ganha essas libs de carona e nem percebe; como aqui não temos
torch de propósito (economia de ~2,5GB e de VRAM), elas vêm dos wheels
`nvidia-cublas-cu12` e `nvidia-cudnn-cu12` — que o pip instala em
`site-packages/nvidia/*/lib/` sem mexer no rpath de ninguém.

Resultado sem este módulo: `Unable to load libcudnn_ops.so.9`, o tropeço
clássico de rodar faster-whisper na GPU sem torch por perto.

A solução é carregar os `.so` com RTLD_GLOBAL antes: uma vez no processo, o
loader reaproveita pelo soname quando o ctranslate2 pedir.
"""

from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# O que o ctranslate2 realmente precisa achar no fim das contas.
SONAMES_EXIGIDOS = ("libcublas.so.12", "libcudnn.so.9")

_resultado: Resultado | None = None


@dataclass
class Resultado:
    ok: bool
    dirs: list[Path] = field(default_factory=list)
    carregadas: int = 0
    faltando: list[str] = field(default_factory=list)
    erro: str = ""

    def ajuda(self) -> str:
        """Mensagem acionável — nunca devolver stack trace cru para o Léo."""
        if self.ok:
            return ""
        if not self.dirs:
            return (
                "Não achei os pacotes CUDA na .venv.\n"
                "  Instale com:  pip install -r requirements.txt\n"
                "  (são nvidia-cublas-cu12 e nvidia-cudnn-cu12, ~1,3GB)"
            )
        caminhos = os.pathsep.join(str(d) for d in self.dirs)
        return (
            "As libs CUDA existem mas não carregaram: "
            + ", ".join(self.faltando)
            + "\n  Tente rodar assim:\n"
            f'    LD_LIBRARY_PATH="{caminhos}:$LD_LIBRARY_PATH" python etapa0.py\n'
            '  Se ainda falhar, troque dispositivo = "cpu" no config.toml para\n'
            "  destravar o teste (vai ficar lento, mas a cadeia roda)."
        )


def _dirs_nvidia() -> list[Path]:
    """Acha os site-packages/nvidia/*/lib/ da .venv atual."""
    dirs: list[Path] = []
    vistos: set[Path] = set()
    for base in sys.path:
        raiz = Path(base) / "nvidia"
        if not raiz.is_dir():
            continue
        for lib in sorted(raiz.glob("*/lib")):
            resolvido = lib.resolve()
            if lib.is_dir() and resolvido not in vistos:
                vistos.add(resolvido)
                dirs.append(lib)
    return dirs


def _carregar_em_passadas(arquivos: list[Path]) -> int:
    """Carrega os .so repetindo enquanto houver progresso.

    Algumas libs dependem de outras (libcudnn.so.9 puxa libcudnn_ops etc.).
    Em vez de fixar uma ordem à mão — que quebra a cada versão nova do cuDNN —
    tentamos todas, guardamos as que falharam e repetimos. Quando uma passada
    inteira não carrega nada novo, é porque o que sobrou não vai mesmo.
    """
    pendentes = list(arquivos)
    carregadas = 0
    while pendentes:
        falharam: list[Path] = []
        for so in pendentes:
            try:
                ctypes.CDLL(str(so), mode=ctypes.RTLD_GLOBAL)
                carregadas += 1
            except OSError:
                falharam.append(so)
        if len(falharam) == len(pendentes):
            break  # passada sem progresso
        pendentes = falharam
    return carregadas


def preparar() -> Resultado:
    """Deixa o CUDA pronto. Idempotente — pode chamar à vontade."""
    global _resultado
    if _resultado is not None:
        return _resultado

    dirs = _dirs_nvidia()
    if not dirs:
        _resultado = Resultado(ok=False, erro="pacotes nvidia-*-cu12 ausentes")
        return _resultado

    # Ajuda qualquer coisa que venha a carregar por soname depois de nós.
    anterior = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(
        [str(d) for d in dirs] + ([anterior] if anterior else [])
    )

    arquivos = sorted(
        so
        for d in dirs
        for so in d.glob("*.so*")
        if so.is_file() and not so.is_symlink()
    )
    carregadas = _carregar_em_passadas(arquivos)

    # O que importa não é quantas carregaram, é se os sonames que o
    # ctranslate2 vai pedir resolvem agora.
    faltando = []
    for soname in SONAMES_EXIGIDOS:
        try:
            ctypes.CDLL(soname, mode=ctypes.RTLD_GLOBAL)
        except OSError:
            faltando.append(soname)

    _resultado = Resultado(
        ok=not faltando,
        dirs=dirs,
        carregadas=carregadas,
        faltando=faltando,
    )
    return _resultado
