"""Fechar programas: "fecha o Discord", "fecha a pasta Downloads".

Fechar é o mesmo que clicar no ×: `wmctrl -c` pede ao programa para fechar, e
ele faz o que faria com o clique — o editor pergunta se quer salvar, o terminal
avisa se há algo rodando. Não é matar o processo. Por isso uma janela só fecha
sem confirmação; **várias janelas do mesmo programa pedem confirmação**
(fechar três janelas do Brave leva junto as abas de todas).

A janela é achada por dois caminhos:
1. o nome falado casa com um programa do catálogo → as janelas da classe dele
   ("terminal" → as janelas do gnome-terminal);
2. senão, o nome casa com o TÍTULO de uma janela ("fecha a pasta Músicas" → a
   janela do Nemo cujo título é Músicas).
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

from .atalhos import nota, normalizar

# Janelas que nunca se fecham por voz.
_PROTEGIDAS = (
    "nemo-desktop",   # a área de trabalho: fechar some com os ícones dela
    "interface.py",   # a janela do próprio Jarvis
    "cinnamon",       # painel e afins
)

_FECHAR = re.compile(
    r"^(?:jarvis[,\s]+)?(?:(?:pode|por favor)[,\s]+)*"
    r"(?:fecha|fechar|feche|encerra|encerrar|encerre|sai do|sai da|sair do|sair da)"
    r"[\s,]+(.+?)(?:[\s,]+(?:pra mim|para mim|por favor|a[íi]))*[.!?]*$",
    re.IGNORECASE,
)
_ESTA = {"essa janela", "esta janela", "janela", "isso", "isso ai", "essa", "esse",
         "esse programa", "este programa", "essa ai", "esse ai"}


@dataclass(frozen=True)
class Janela:
    id: str
    classe: str   # "brave-browser.Brave-browser"
    titulo: str


def pedido_de_fechar(falado: str) -> str | None:
    """O que mandaram fechar, ou None se a frase não é "fecha X"."""
    m = _FECHAR.match(falado.strip())
    if not m:
        return None
    alvo = m.group(1).strip()
    # "fecha o Brave" → "Brave"; o artigo não é nome.
    alvo = re.sub(r"^(?:o|a|os|as|um|uma)\s+", "", alvo, flags=re.IGNORECASE)
    # "a pasta Músicas", "o programa do Discord", "a janela do terminal": a
    # palavra de categoria não é nome.
    alvo = re.sub(r"^(?:pasta|programa|aplicativo|app|janela)(?:\s+(?:do|da|de))?\s+", "",
                  alvo, flags=re.IGNORECASE)
    return alvo or None


def e_a_janela_ativa(alvo: str) -> bool:
    return normalizar(alvo) in {normalizar(e) for e in _ESTA}


def abertas() -> list[Janela]:
    try:
        saida = subprocess.run(["wmctrl", "-lx"], capture_output=True,
                               text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    janelas = []
    for linha in saida.splitlines():
        partes = linha.split(None, 4)
        if len(partes) < 4:
            continue
        id_, _mesa, classe = partes[0], partes[1], partes[2]
        titulo = partes[4] if len(partes) > 4 else ""
        if any(p in classe.lower() for p in _PROTEGIDAS):
            continue
        janelas.append(Janela(id_, classe, titulo))
    return janelas


def ativa() -> Janela | None:
    try:
        saida = subprocess.run(["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                               capture_output=True, text=True, timeout=3).stdout
        id_ = int(saida.rsplit("#", 1)[1].split(",")[0].strip(), 16)
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None
    for j in abertas():
        if int(j.id, 16) == id_:
            return j
    return None


def da_classe(classe: str) -> list[Janela]:
    classe = classe.lower()
    return [j for j in abertas() if classe and classe in j.classe.lower()]


def por_titulo(falado: str, minimo: float = 0.75) -> list[Janela]:
    """Janelas cujo título casa com o que foi falado, a melhor primeiro."""
    alvo = normalizar(falado)
    notas = []
    for j in abertas():
        # O título do Brave termina em " - Brave", o do VS Code em
        # " - Visual Studio Code": o nome do programa conta como título também.
        candidatos = [normalizar(j.titulo), *(normalizar(p) for p in j.titulo.split(" - "))]
        n = max((nota(alvo, c) for c in candidatos if c), default=0.0)
        if n >= minimo:
            notas.append((n, j))
    notas.sort(key=lambda p: -p[0])
    if not notas:
        return []
    melhor = notas[0][0]
    return [j for n, j in notas if n >= melhor - 0.02]


def fechar(janelas: list[Janela]) -> int:
    """Pede para cada janela fechar, como o ×. Devolve quantas pediu."""
    feitas = 0
    for j in janelas:
        try:
            subprocess.run(["wmctrl", "-i", "-c", j.id], timeout=3, check=False)
            feitas += 1
        except (OSError, subprocess.SubprocessError):
            pass
    return feitas
