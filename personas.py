"""Carrega a persona ativa. Um arquivo por humor, em jarvis/personas/."""
from pathlib import Path

PASTA = Path(__file__).parent / "personas"
PADRAO = "jarvis"
_atual = PADRAO


def definir(nome: str) -> str:
    global _atual
    if not (PASTA / f"persona_{nome}.md").exists():
        raise FileNotFoundError(nome)
    _atual = nome
    return _atual


def atual() -> str:
    return _atual


def texto() -> str:
    arquivo = PASTA / f"persona_{_atual}.md"
    return (arquivo if arquivo.exists() else PASTA / f"persona_{PADRAO}.md").read_text(encoding="utf-8")


def lista() -> list[str]:
    return sorted(p.stem.removeprefix("persona_") for p in PASTA.glob("persona_*.md"))