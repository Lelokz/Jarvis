"""Tela 2 do instalador ("Seu PC"): confere as peças que a NOVA usa, sem
instalar nada. Só biblioteca padrão: roda antes de a NOVA existir no PC.

A placa decide as vozes: NVIDIA com 8 GB ou mais leva as dubladas (a NOVA usa
~5,8 GB da placa do Léo: ouvido 2,8 + Friday 2,0 + Jarvis 1,0); senão, as leves.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import urllib.request
from pathlib import Path

VRAM_DUBLADAS_GB = 8
WINDOWS = os.name == "nt"
# No Windows, cada programa de terminal que o instalador chama abriria uma janela preta.
SEM_JANELA = {"creationflags": subprocess.CREATE_NO_WINDOW} if WINDOWS else {}


def _rodar(*cmd: str, teto: float = 5.0) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=teto, **SEM_JANELA)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def sistema() -> dict:
    nome = platform.system()
    if nome == "Linux":
        for linha in Path("/etc/os-release").read_text(errors="ignore").splitlines() if Path("/etc/os-release").exists() else []:
            if linha.startswith("PRETTY_NAME="):
                nome = linha.split("=", 1)[1].strip('"')
    elif nome == "Windows":
        nome = f"Windows {platform.release()}"
    bits64 = platform.machine().lower() in ("x86_64", "amd64", "aarch64", "arm64")
    return {"id": "sistema", "rotulo": "Sistema", "valor": f"{nome} · {'64' if bits64 else '32'} bits",
            "ok": bits64, "nota": "ok" if bits64 else "precisa de 64 bits"}


def placa() -> dict:
    saida = _rodar("nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits")
    if saida.strip():
        nome, mb = [p.strip() for p in saida.splitlines()[0].split(",")]
        gb = round(int(float(mb)) / 1024)
        dubladas = gb >= VRAM_DUBLADAS_GB
        return {"id": "placa", "rotulo": "Placa de vídeo", "valor": f"{nome} · {gb} GB", "ok": True,
                "nota": "vozes dubladas" if dubladas else "vozes leves", "dubladas": dubladas, "nvidia": True}
    # Sem NVIDIA: o nome da placa só para mostrar (a NOVA roda no processador).
    nome = ""
    if WINDOWS:
        nome = _rodar("powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController).Name",
                      teto=10).strip().split("\n")[0].strip()
    for linha in [] if WINDOWS else _rodar("lspci").splitlines():
        if " VGA " in linha or "3D controller" in linha:
            nome = linha.split(": ", 1)[-1]
            break
    return {"id": "placa", "rotulo": "Placa de vídeo", "valor": nome or "sem placa NVIDIA", "ok": True,
            "nota": "vozes leves", "dubladas": False, "nvidia": False}


def _memoria_windows() -> int:
    import ctypes

    class Estado(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    e = Estado(dwLength=ctypes.sizeof(Estado))
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(e))
    return round(e.ullTotalPhys / 1024 ** 3)


def memoria() -> dict:
    gb = 0
    try:
        if WINDOWS:
            gb = _memoria_windows()
        for linha in [] if WINDOWS else Path("/proc/meminfo").read_text().splitlines():
            if linha.startswith("MemTotal:"):
                gb = round(int(linha.split()[1]) / 1024 / 1024)
    except OSError:
        pass
    ok = gb >= 8 or gb == 0
    return {"id": "memoria", "rotulo": "Memória", "valor": f"{gb} GB" if gb else "não consegui ver",
            "ok": ok, "nota": "ok" if ok else "pouca: vai ficar lenta"}


def _microfones_windows() -> list[str]:
    """Os microfones ligados, como aparecem nas configurações de som do Windows
    ("Microfone (fifine Microphone)"), lidos do registro (sem administrador)."""
    import winreg
    nomes = []
    base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as captura:
        for i in range(winreg.QueryInfoKey(captura)[0]):
            guid = winreg.EnumKey(captura, i)
            try:
                with winreg.OpenKey(captura, guid) as aparelho:
                    if winreg.QueryValueEx(aparelho, "DeviceState")[0] != 1:   # 1 = ativo
                        continue
                with winreg.OpenKey(captura, guid + r"\Properties") as props:
                    tipo = winreg.QueryValueEx(props, "{a45c254e-df1c-4efd-8020-67d146a850e0},2")[0]
                    placa = winreg.QueryValueEx(props, "{b3f8fa53-0004-438e-9003-51a46e139bfc},6")[0]
            except OSError:
                continue
            nomes.append(f"{tipo} ({placa})")
    return nomes


def microfone() -> dict:
    if WINDOWS:
        try:
            mics = _microfones_windows()
        except OSError:
            return {"id": "microfone", "rotulo": "Microfone", "valor": "não consegui ver", "ok": True,
                    "nota": "testa na tela 6"}
        if not mics:
            return {"id": "microfone", "rotulo": "Microfone", "valor": "nenhum achado", "ok": False,
                    "nota": "liga um e confere de novo"}
        return {"id": "microfone", "rotulo": "Microfone", "ok": True, "nota": "ok",
                "valor": mics[0] + (f" e mais {len(mics) - 1}" if len(mics) > 1 else "")}
    padrao = _rodar("pactl", "get-default-source").strip()
    try:
        fontes = json.loads(_rodar("pactl", "-f", "json", "list", "sources") or "[]")
    except ValueError:
        fontes = []
    # Os "monitor" são o som que SAI (para gravar a tela), não microfone.
    mics = [f for f in fontes if not f.get("name", "").endswith(".monitor") and f.get("monitor_of_sink") in (None, "n/a")]
    escolhido = next((f for f in mics if f.get("name") == padrao), mics[0] if mics else None)
    if escolhido is None:
        return {"id": "microfone", "rotulo": "Microfone", "valor": "nenhum achado", "ok": False,
                "nota": "liga um e confere de novo"}
    return {"id": "microfone", "rotulo": "Microfone", "valor": f"{escolhido.get('description', 'microfone')} (padrão)",
            "ok": True, "nota": "ok"}


def internet() -> dict:
    try:
        urllib.request.urlopen("https://github.com", timeout=6).close()
        ok = True
    except OSError:
        ok = False
    return {"id": "internet", "rotulo": "Internet", "valor": "Conectado" if ok else "sem conexão",
            "ok": ok, "nota": "ok" if ok else "precisa para baixar"}


def disco(pasta: str) -> dict:
    """Quanto cabe onde a pessoa quer instalar (sobe até achar uma pasta que existe)."""
    p = Path(pasta).expanduser()
    while not p.exists() and p != p.parent:
        p = p.parent
    livre = shutil.disk_usage(p).free / 1e9
    return {"livre_gb": round(livre)}


def tudo() -> dict:
    itens = [sistema(), placa(), memoria(), microfone(), internet()]
    return {"itens": itens, "dubladas": itens[1].get("dubladas", False), "nvidia": itens[1].get("nvidia", False),
            "pode": all(i["ok"] for i in itens if i["id"] in ("sistema", "internet"))}


if __name__ == "__main__":
    print(json.dumps(tudo(), ensure_ascii=False, indent=1))
