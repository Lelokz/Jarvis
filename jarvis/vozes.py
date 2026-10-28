"""Onde estão as vozes dubladas (o timbre do Jarvis e a Friday), em qualquer PC.

O instalador baixa o pacote de vozes na pasta que a pessoa escolher e anota o
caminho em ajustes.json ("pasta_vozes"). Dentro do pacote vai uma etiqueta,
`nova-vozes.json`: se a pasta mudar de lugar, a NOVA procura a etiqueta na
pasta pessoal e nos outros discos e se acha sozinha. Sem achar, fala com a
voz reserva (a Kokoro) e Ajustes → Voz e som mostra "Procurar pasta".

O pacote:
    <pasta>/nova-vozes.json
    <pasta>/jarvis/rvc/jarvis-dublado.pth e .index   (o timbre, servidor_rvc.py)
    <pasta>/friday/modelo/friday-emilia-v1.safetensors, vocab.txt
    <pasta>/friday/ref/...                           (servidor_friday.py --pasta)

O jarvis.sh pergunta aqui (`python -m jarvis.vozes --shell`) antes de ligar
os servidores de voz; no Windows, o jarvis/ligar.py chama achar() e programas().
"""

from __future__ import annotations

import json
import os
import shlex
import sys
import time
from pathlib import Path

from jarvis import ajustes

MARCA = "nova-vozes.json"
# O PC do Léo, de antes do pacote: as duas vozes soltas em ~/.local/share/jarvis.
ANTIGA = Path.home() / ".local/share/jarvis"
ARQ_JARVIS = Path("rvc/jarvis-dublado.pth")
ARQ_FRIDAY = Path("modelo/friday-emilia-v1.safetensors")
# Pastas que nunca têm o pacote e só atrasam a busca.
PULAR = {"node_modules", "venv", ".venv", "__pycache__", "site-packages", "proc", "sys", "snap"}


def _do_pacote(pasta: Path) -> dict[str, Path | None]:
    jarvis, friday = pasta / "jarvis", pasta / "friday"
    return {"jarvis": jarvis if (jarvis / ARQ_JARVIS).is_file() else None,
            "friday": friday if (friday / ARQ_FRIDAY).is_file() else None}


def _eh_pacote(pasta: Path) -> bool:
    return (pasta / MARCA).is_file()


def _procurar(teto_s: float = 8.0) -> Path | None:
    """A etiqueta na pasta pessoal (até 4 níveis) e nos outros discos (até 3)."""
    fim = time.monotonic() + teto_s
    raizes = [(Path.home(), 4)]
    if os.name == "nt":
        # Os outros discos do Windows (D:\, E:\...).
        raizes += [(Path(d), 3) for d in os.listdrives() if Path(d) != Path(Path.home().anchor)]
    for montagens in () if os.name == "nt" else (
            Path("/mnt"), Path("/media") / os.environ.get("USER", ""), Path("/run/media") / os.environ.get("USER", "")):
        try:
            raizes += [(d, 3) for d in montagens.iterdir() if d.is_dir()]
        except OSError:
            pass
    for raiz, fundo in raizes:
        fila = [(raiz, 0)]
        while fila:
            if time.monotonic() > fim:
                return None
            pasta, nivel = fila.pop(0)
            if _eh_pacote(pasta):
                return pasta
            if nivel >= fundo:
                continue
            try:
                filhas = [d for d in pasta.iterdir()
                          if d.is_dir() and not d.is_symlink() and not d.name.startswith(".") and d.name not in PULAR]
            except OSError:
                continue
            fila += [(d, nivel + 1) for d in filhas]
    return None


def achar(procurar: bool = False) -> dict:
    """{"jarvis": pasta|None, "friday": pasta|None, "pasta": pacote|None}.
    `procurar`: se a anotada sumiu, varre os discos (lento; não usar na hora de um pedido)."""
    anotada = ajustes.ler()["pasta_vozes"]
    if anotada and _eh_pacote(Path(anotada)):
        return {**_do_pacote(Path(anotada)), "pasta": Path(anotada)}
    # O PC de antes do pacote (o do Léo).
    antiga = {"jarvis": ANTIGA / "voz-jarvis" if (ANTIGA / "voz-jarvis" / ARQ_JARVIS).is_file() else None,
              "friday": ANTIGA / "voz-friday" if (ANTIGA / "voz-friday" / ARQ_FRIDAY).is_file() else None}
    if antiga["jarvis"] or antiga["friday"]:
        return {**antiga, "pasta": None}
    # Só procura se ela JÁ teve uma pasta (moveu de lugar): num PC sem as vozes
    # dubladas, a busca só atrasaria o ligar.
    if procurar and anotada:
        achada = _procurar()
        if achada is not None:
            ajustes.mudar(pasta_vozes=str(achada))
            return {**_do_pacote(achada), "pasta": achada}
    return {"jarvis": None, "friday": None, "pasta": None}


def escolher(pasta: str) -> dict:
    """O "Procurar pasta" da janela: aceita a pasta do pacote ou uma de dentro dela."""
    p = Path(pasta).expanduser()
    for candidata in (p, p.parent, p.parent.parent):
        if _eh_pacote(candidata):
            ajustes.mudar(pasta_vozes=str(candidata))
            return estado()
    return {**estado(), "detalhe": "Essa pasta não tem as vozes da NOVA (falta o nova-vozes.json)."}


def programas() -> dict[str, Path] | None:
    """Os programas que tocam as vozes, se foi o instalador que pôs: um ambiente só para
    as duas, a parte de tocar do Applio e (só no Windows) o FFmpeg. Sem eles, None."""
    base = Path(ajustes.ler()["programas_vozes"] or "/nao-existe")
    python = base / "vozes" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        return None
    return {"python": python, "applio": base / "applio", "ffmpeg": base / "ffmpeg" / "bin"}


def estado() -> dict:
    """Para Ajustes → Voz e som (janela e app)."""
    v = achar()
    return {"jarvis": v["jarvis"] is not None, "friday": v["friday"] is not None,
            "pasta": str(v["pasta"] or v["jarvis"] or v["friday"] or "")}


if __name__ == "__main__":
    if sys.argv[1:] == ["--shell"]:
        v = achar(procurar=True)
        print(f"VOZ_JARVIS={shlex.quote(str(v['jarvis'] or ''))}")
        print(f"VOZ_FRIDAY={shlex.quote(str(v['friday'] or ''))}")
        # Os programas que tocam as vozes, se foi o instalador que pôs (um ambiente só
        # para as duas, e a parte de tocar do Applio). Sem isso, o jarvis.sh usa os de antes.
        p = programas()
        if p is not None:
            print(f"VOZ_PY={shlex.quote(str(p['python']))}")
            print(f"APPLIO={shlex.quote(str(p['applio']))}")
            print(f"APPLIO_PY={shlex.quote(str(p['python']))}")
        from jarvis import config
        print(f"WHISPER={shlex.quote(config.carregar().stt.modelo)}")
    else:
        print(json.dumps(estado(), ensure_ascii=False))
