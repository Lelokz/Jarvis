"""python -m jarvis.monitor [--json | --janela]"""

from __future__ import annotations

import json
import sys
import time

from jarvis.monitor.leitura import Monitor, nivel

PALAVRA = ("tranquilo", "puxado", "NO LIMITE")


def _gb(x: float) -> str:
    return f"{x:.1f}".replace(".", ",") + " GB"


def resumo(d: dict) -> str:
    linhas = []
    g = d["gpu"]
    if g:
        n = max(nivel(g["uso"], "uso"), nivel(g["temp"], "temp_gpu"))
        linhas.append(f'Placa de vídeo ({g["nome"]}): {g["uso"]:.0f}% de uso, {g["temp"]:.0f} °C, '
                      f'{_gb(g["memoria_usada"])} de {_gb(g["memoria_total"])} de memória [{PALAVRA[n]}]')
    c = d["cpu"]
    temp = f', {c["temp"]:.0f} °C' if c["temp"] is not None else ""
    n = max(nivel(c["uso"], "uso"), nivel(c["temp"], "temp_cpu"))
    linhas.append(f'Processador ({c["nome"]}): {c["uso"]:.0f}% de uso{temp} [{PALAVRA[n]}]')
    r = d["ram"]
    n = nivel(100 * r["usada"] / r["total"], "ram")
    linhas.append(f'RAM: {_gb(r["usada"])} em uso de {_gb(r["total"])}, {_gb(r["cache"])} em cache, '
                  f'{_gb(r["livre"])} livre ({_gb(r["disponivel"])} disponíveis contando o cache) [{PALAVRA[n]}]')
    for k in d["discos"]:
        papel = f' ({k["papel"]})' if k["papel"] else ""
        linhas.append(f'{k["titulo"]}{papel}: {k["pct"]:.0f}% usado, {k["usado"]:.0f} de {k["total"]:.0f} GB, '
                      f'{k["livre"]:.0f} GB livres [{PALAVRA[nivel(k["pct"], "disco")]}]')
    return "\n".join(linhas)


def main(args: list[str]) -> int:
    if args[:1] == ["--janela"]:
        from jarvis.monitor.janela import abrir
        return abrir(args[2] if args[1:2] == ["--retrato"] else None)
    m = Monitor()
    time.sleep(0.5)   # o uso do processador precisa de duas leituras
    d = m.ler()
    print(json.dumps(d, ensure_ascii=False, indent=1) if args[:1] == ["--json"] else resumo(d))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
