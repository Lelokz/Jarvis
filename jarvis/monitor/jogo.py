"""O modo jogo (08/11/2026): o Jarvis percebe que o Léo está jogando pelos
processos (não pela tela cheia: vídeo em tela cheia não é jogo).

Contam como jogo:
- Roblox: o Sober (flatpak);
- Steam: o `reaper SteamLaunch AppId=…` que a Steam põe na frente de todo jogo
  (o nome sai do appmanifest);
- jogo de Windows pelo Wine/Proton (Epic, GOG, Hydra, Twintail): um `.exe`
  que não seja peça do próprio Wine ou de um launcher;
- Minecraft: o Java do jogo (os argumentos dele têm `--assetIndex`).

Enquanto ele joga, o que o Jarvis roda (e o que esses programas abrirem) fica
nos últimos núcleos do processador, para não disputar com o jogo: `aliviar()`.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

NUCLEOS_LEVES = {5, 6, 7}

BIBLIOTECAS_STEAM = (Path.home() / ".steam/debian-installation/steamapps",
                     Path("/mnt/cab1286d-6765-4c73-9c77-8d3119b4b644/SteamLibrary/steamapps"))
# Peças do Wine/Proton e de launchers: rodam .exe, mas não são o jogo.
NAO_E_JOGO = {
    "explorer", "services", "winedevice", "plugplay", "svchost", "rpcss", "tabtip", "start",
    "conhost", "wineboot", "winemenubuilder", "rundll32", "steam", "steamwebhelper", "steamservice",
    "epicgameslauncher", "epicwebhelper", "galaxyclient", "galaxyclienthelper", "galaxycommunication",
    "crashreportclient", "unitycrashhandler64", "unitycrashhandler32", "easyanticheat",
    "easyanticheat_eos_setup", "redprelauncher", "redlauncher", "cmd", "regedit", "msiexec",
    "setup", "installer", "uninstall", "vc_redist.x64", "vc_redist.x86", "dxsetup", "dotnetfx",
}
NOMES_EXE = {"cyberpunk2077": "Cyberpunk 2077"}
_APPID = re.compile(r"AppId=(\d+)")


def _nome_steam(appid: str) -> str:
    for biblioteca in BIBLIOTECAS_STEAM:
        try:
            texto = (biblioteca / f"appmanifest_{appid}.acf").read_text(errors="ignore")
        except OSError:
            continue
        m = re.search(r'"name"\s+"([^"]+)"', texto)
        if m:
            return m.group(1)
    return "um jogo da Steam"


def _cmdline(pid: str) -> list[str]:
    try:
        return [p.decode(errors="ignore") for p in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0") if p]
    except OSError:
        return []


def jogando() -> str | None:
    """O nome do jogo aberto, ou None."""
    achado = None
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        args = _cmdline(p)
        if not args:
            continue
        primeiro = args[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
        if primeiro in ("sober",):
            return "Roblox"
        if primeiro == "reaper" and "SteamLaunch" in args:
            m = next((_APPID.search(a) for a in args if _APPID.search(a)), None)
            return _nome_steam(m.group(1)) if m else "um jogo da Steam"
        if primeiro in ("java", "javaw") and "--assetIndex" in args:
            achado = achado or "Minecraft"
            continue
        if primeiro.endswith(".exe"):
            base = primeiro[:-4]
            if base not in NAO_E_JOGO and not base.startswith(("wine", "proton")):
                achado = achado or NOMES_EXE.get(base, args[0].replace("\\", "/").rsplit("/", 1)[-1][:-4])
    return achado


def _descendentes(raiz: int) -> list[int]:
    filhos: dict[int, list[int]] = {}
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            for linha in Path(f"/proc/{p}/status").read_text().splitlines():
                if linha.startswith("PPid:"):
                    filhos.setdefault(int(linha.split()[1]), []).append(int(p))
                    break
        except (OSError, ValueError):
            continue
    saida, pilha = [], [raiz]
    while pilha:
        for f in filhos.get(pilha.pop(), []):
            saida.append(f)
            pilha.append(f)
    return saida


def aliviar(raiz: int, ligar: bool) -> None:
    """Põe (ou tira) os processos que `raiz` abriu nos núcleos leves. Todas as
    threads de cada um; o que eles abrirem depois herda. O próprio `raiz` (o
    assistente, que escuta o microfone) fica onde está."""
    nucleos = NUCLEOS_LEVES if ligar else set(range(os.cpu_count() or 8))
    for pid in _descendentes(raiz):
        try:
            for tid in os.listdir(f"/proc/{pid}/task"):
                os.sched_setaffinity(int(tid), nucleos)
        except OSError:
            continue
