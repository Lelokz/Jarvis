"""As personas do Léo (09/11/2026): um arquivo por jeito, em jarvis/personas/.

- `persona_jarvis.md` e `persona_friday.md`: o jeito de cada um falando com o
  Léo (entram nas instruções do agente, sempre).
- Os outros (`senhor`, `bebado`, ...) são MODOS que ele liga por voz ("modo
  senhor", "volta ao normal"). O modo escolhido fica num arquivo, porque quem
  troca é o Claude por um comando (outro processo) e o agente lê a cada pedido.

Só valem na conversa com o Léo (PC, celular, relógio). Os grupos do WhatsApp
têm o jeito deles (jarvis/grupo/persona_grupo.md).

    python -m jarvis.personas lista | atual | definir <modo> | normal
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PASTA = Path(__file__).parent
BASES = ("jarvis", "friday")   # o jeito de cada um, sempre ligado
NORMAL = "normal"              # sem modo
_DADOS = Path(os.environ.get("JARVIS_DADOS", Path.home() / ".local/share/jarvis"))


def _arquivo_do_modo() -> Path:
    return _DADOS / "persona-modo.txt"


def lista() -> list[str]:
    return sorted(p.stem.removeprefix("persona_") for p in PASTA.glob("persona_*.md"))


def modos() -> list[str]:
    return [n for n in lista() if n not in BASES]


def texto(nome: str) -> str:
    arquivo = PASTA / f"persona_{nome}.md"
    return arquivo.read_text(encoding="utf-8").strip() if arquivo.exists() else ""


def atual() -> str:
    """O modo ligado agora, ou "normal"."""
    try:
        nome = _arquivo_do_modo().read_text(encoding="utf-8").strip()
    except OSError:
        return NORMAL
    return nome if nome in modos() else NORMAL


def definir(nome: str) -> str:
    nome = nome.strip().lower().replace("ê", "e")
    if nome in (NORMAL, "jarvis", "friday", ""):
        _arquivo_do_modo().unlink(missing_ok=True)
        return NORMAL
    if nome not in modos():
        raise FileNotFoundError(nome)
    _arquivo_do_modo().parent.mkdir(parents=True, exist_ok=True)
    _arquivo_do_modo().write_text(nome, encoding="utf-8")
    return nome


def para_instrucoes() -> str:
    """O bloco que entra nas instruções do agente."""
    partes = ["## O jeito de vocês com o {usuario} (as personas dele, 09/11/2026)",
              "",
              "O {usuario} escreveu como quer cada um. Vale na conversa com ele (voz, "
              "digitado, celular, relógio); onde contradiz o que está acima, vale isto. "
              "Mensagens que você manda para outras pessoas e os grupos do WhatsApp "
              "seguem o jeito de sempre.",
              ""]
    for base in BASES:
        if texto(base):
            partes += [texto(base).replace("# Persona:", "### Persona:"), ""]
    if modos():
        partes += ["### Modos",
                   "",
                   "Quando o cabeçalho da mensagem tiver `MODO <nome>`, o jeito daquele "
                   "modo vale por cima de tudo. Ele liga por voz (\"modo senhor\", \"fica "
                   "bêbado\") e desliga (\"volta ao normal\"): rode `cd ~/Projetos/Jarvis && "
                   ".venv/bin/python -m jarvis.personas definir <modo>` (ou `normal`).",
                   ""]
        for m in modos():
            partes += [texto(m).replace("# Persona:", "#### Modo:"), ""]
    return "\n".join(partes).strip()


def main(a: list[str]) -> int:
    if not a or a[0] == "lista":
        print("bases:", ", ".join(BASES), "| modos:", ", ".join(modos()))
    elif a[0] == "atual":
        print(atual())
    elif a[0] == "normal":
        print(definir(NORMAL))
    elif a[0] == "definir" and len(a) > 1:
        try:
            print(definir(a[1]))
        except FileNotFoundError:
            print(f"não existe o modo {a[1]!r}; tem: {', '.join(modos())}")
            return 1
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
