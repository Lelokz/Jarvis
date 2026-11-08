"""python -m jarvis.organizador … (ver jarvis/organizador/__init__.py)"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from jarvis.organizador import nucleo


def main(a: list[str]) -> int:
    if a[:1] == ["organizar"] and len(a) == 2:
        print(json.dumps(nucleo.organizar(Path(a[1]).resolve()), ensure_ascii=False, indent=1))
    elif a[:1] == ["mover"] and len(a) == 4:
        item = Path(a[1]).resolve()
        rel = nucleo.ler_pendentes().get(str(item), {}).get("relatorio", "")
        print(json.dumps(nucleo.mover(item, Path(a[2]), a[3], rel or "pelo Léo"), ensure_ascii=False))
    elif a[:1] == ["pendentes"]:
        p = nucleo.ler_pendentes()
        for item, d in p.items():
            print(f'{item}\n    {d["pergunta"]}\n    ({d["relatorio"]})')
        if not p:
            print("nada esperando resposta")
    elif a[:1] == ["desfazer"] and a[1:] in (["ultimo"], ["hoje"]):
        lista = nucleo.movidos()
        if a[1] == "ultimo":
            print(nucleo.devolver(lista[-1]) if lista else "nada para desfazer")
        else:
            hoje = [d for d in lista if d["quando"].startswith(date.today().isoformat())]
            for d in reversed(hoje):
                print(nucleo.devolver(d))
            if not hoje:
                print("nada movido hoje")
    else:
        for d in nucleo.movidos()[-20:]:
            print(f'{d["quando"]}  {Path(d["origem"]).name}\n    -> {d["destino"]}\n    {d["relatorio"]}\n')
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
