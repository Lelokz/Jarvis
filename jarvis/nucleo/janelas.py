"""Fechar e mexer em janelas: "fecha o Discord", "minimiza o terminal",
"põe o Brave na frente", "maximiza essa janela", "mostra a área de trabalho".

Mexer (trazer, minimizar, maximizar, restaurar) é inofensivo e não pergunta.

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


# Mexer em janela: (ação, padrão). O alvo é o grupo 1; "essa janela" vale.
_MEXER = [
    ("trazer", re.compile(
        r"^(?:p[õo]e|coloca|bota|traz)[\s,]+(.+?)[\s,]+(?:na frente|pra frente|para frente|aqui)$"
        r"|^(?:vai|muda|troca|alterna|volta)[\s,]+(?:pro|pra|para o|para a|para)[\s,]+(.+)$"
        r"|^foca[\s,]+(?:no|na|em)[\s,]+(.+)$", re.IGNORECASE)),
    ("minimizar", re.compile(r"^(?:minimiza|minimizar|minimize|esconde|esconder)[\s,]+(.+)$",
                             re.IGNORECASE)),
    ("maximizar", re.compile(
        r"^(?:maximiza|maximizar|maximize)[\s,]+(.+)$"
        r"|^aumenta[\s,]+(?:a )?janela(?:[\s,]+(?:do|da|de))?[\s,]+(.+)$", re.IGNORECASE)),
    ("restaurar", re.compile(
        r"^(?:restaura|restaurar|desmaximiza|desmaximizar)[\s,]+(.+)$"
        r"|^diminui[\s,]+(?:a )?janela(?:[\s,]+(?:do|da|de))?[\s,]+(.+)$", re.IGNORECASE)),
]
_AREA = {"minimiza tudo", "minimizar tudo", "esconde tudo", "mostra area trabalho",
         "mostrar area trabalho", "limpa tela", "minimiza todas janelas",
         "minimiza todas", "vai pra area trabalho", "vai para area trabalho"}
_AREA_VOLTA = {"volta janelas", "traz janelas volta", "mostra janelas", "volta tudo",
               "desminimiza tudo", "mostra janelas de novo", "traz janelas de volta"}


def _limpar_fala(falado: str) -> str:
    texto = re.sub(r"^jarvis[,\s]+", "", falado.strip(), flags=re.IGNORECASE)
    texto = re.sub(r"^(?:(?:pode|por favor)[,\s]+)+", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"(?:[\s,]+(?:pra mim|para mim|por favor|a[íi]))+[.!?]*$", "", texto,
                   flags=re.IGNORECASE)
    return texto.strip().rstrip(".!?").strip()


def _limpar_alvo(alvo: str) -> str:
    alvo = re.sub(r"^(?:o|a|os|as|um|uma)\s+", "", alvo.strip(), flags=re.IGNORECASE)
    alvo = re.sub(r"^(?:pasta|programa|aplicativo|app|janela)(?:\s+(?:do|da|de))?\s+", "",
                  alvo, flags=re.IGNORECASE)
    return alvo.strip()


def pedido_de_mexer(falado: str) -> tuple[str, str | None] | None:
    """("trazer"|"minimizar"|"maximizar"|"restaurar", alvo), ("area"|"area_volta",
    None), ou None se a frase não é sobre janela."""
    texto = _limpar_fala(falado)
    chave = normalizar(texto)
    if chave in {normalizar(f) for f in _AREA}:
        return ("area", None)
    if chave in {normalizar(f) for f in _AREA_VOLTA}:
        return ("area_volta", None)
    for acao, padrao in _MEXER:
        m = padrao.match(texto)
        if m:
            alvo = _limpar_alvo(next(g for g in m.groups() if g))
            return (acao, alvo) if alvo else None
    return None


def pedido_de_fechar(falado: str) -> str | None:
    """O que mandaram fechar, ou None se a frase não é "fecha X"."""
    m = _FECHAR.match(falado.strip())
    if not m:
        return None
    # "fecha o Brave" → "Brave"; "a pasta Músicas" → "Músicas": artigo e
    # palavra de categoria não são nome.
    return _limpar_alvo(m.group(1)) or None


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


def _wmctrl(*args: str) -> None:
    try:
        subprocess.run(["wmctrl", *args], timeout=3, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


def trazer(j: Janela) -> None:
    """Traz para a frente: desminimiza, muda de área de trabalho se preciso, foca."""
    _wmctrl("-i", "-a", j.id)


def maximizar(j: Janela) -> None:
    _wmctrl("-i", "-r", j.id, "-b", "add,maximized_vert,maximized_horz")
    trazer(j)


def restaurar(j: Janela) -> None:
    _wmctrl("-i", "-r", j.id, "-b", "remove,maximized_vert,maximized_horz")
    trazer(j)


def minimizar(j: Janela) -> None:
    """O `wmctrl` não minimiza no Cinnamon (medido: `-b add,hidden` não faz
    nada). O jeito padrão (ICCCM) é pedir ao gerenciador de janelas a troca
    para o estado Iconic, que é o que o botão de minimizar faz."""
    try:
        from Xlib import X, display, protocol
        d = display.Display()
        w = d.create_resource_object("window", int(j.id, 16))
        ev = protocol.event.ClientMessage(
            window=w, client_type=d.intern_atom("WM_CHANGE_STATE"),
            data=(32, [3, 0, 0, 0, 0]))  # 3 = IconicState
        d.screen().root.send_event(
            ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        d.flush()
        d.close()
    except Exception:  # sem X, sem a lib: não derruba a conversa
        pass


def area_de_trabalho(mostrar: bool) -> None:
    """Esconde todas as janelas (como o canto da tela) ou traz de volta."""
    _wmctrl("-k", "on" if mostrar else "off")


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
