"""Lê os números do PC. Só Linux, só biblioteca padrão (+ o nvidia-smi do driver)."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

GIB = 1024 ** 3

# O que mora em cada disco, pelo ponto de montagem. Sem entrada: aparece o modelo.
# HD novo (1 TB, ~23/11/2026): revisar com o Léo a ordem e estes nomes.
PAPEIS = {
    "/": "sistema",
    "/mnt/cab1286d-6765-4c73-9c77-8d3119b4b644": "jogos e gravações",
}
# Partição menor que isto não é disco de verdade para o Léo (a /boot/efi).
MINIMO = 5 * GIB

# Acima do primeiro número fica amarelo ("Puxado"), acima do segundo, vermelho
# ("No limite"). A janela e o resumo falado usam os mesmos.
LIMITES = {
    "uso": (70, 90),          # placa e processador, %
    "temp_gpu": (70, 83),     # °C
    "temp_cpu": (70, 85),     # °C
    "ram": (75, 90),          # % em uso
    "disco": (80, 90),        # % usado
}


def nivel(valor: float | None, chave: str) -> int:
    """0 tranquilo, 1 puxado, 2 no limite."""
    if valor is None:
        return 0
    amarelo, vermelho = LIMITES[chave]
    return 2 if valor >= vermelho else 1 if valor >= amarelo else 0


# ---------- processador ----------

def _tempos_cpu() -> tuple[int, int]:
    campos = [int(x) for x in Path("/proc/stat").read_text().split("\n", 1)[0].split()[1:]]
    ocioso = campos[3] + campos[4]   # idle + iowait
    return ocioso, sum(campos[:8])


class Processador:
    """O uso é a diferença entre duas leituras: guarda a anterior."""

    def __init__(self) -> None:
        self._antes = _tempos_cpu()
        self.nome = self._nome()
        self.nucleos = os.cpu_count() or 0

    @staticmethod
    def _nome() -> str:
        for linha in Path("/proc/cpuinfo").read_text().splitlines():
            if linha.startswith("model name"):
                nome = linha.split(":", 1)[1].strip()
                for sobra in (" with Radeon Vega Graphics", " with Radeon Graphics", "AMD ", "Intel(R) Core(TM) "):
                    nome = nome.replace(sobra, "")
                return nome.strip()
        return "Processador"

    def uso(self) -> float:
        ocioso, total = _tempos_cpu()
        d_ocioso, d_total = ocioso - self._antes[0], total - self._antes[1]
        self._antes = (ocioso, total)
        return 0.0 if d_total <= 0 else max(0.0, min(100.0, 100 * (1 - d_ocioso / d_total)))


def temp_cpu() -> float | None:
    """k10temp (AMD: Tctl/Tdie) ou coretemp (Intel: Package)."""
    for hw in Path("/sys/class/hwmon").glob("hwmon*"):
        try:
            nome = (hw / "name").read_text().strip()
        except OSError:
            continue
        if nome not in ("k10temp", "coretemp", "zenpower"):
            continue
        for entrada in sorted(hw.glob("temp*_input")):
            rotulo = entrada.with_name(entrada.name.replace("_input", "_label"))
            texto = rotulo.read_text().strip() if rotulo.exists() else ""
            if texto in ("Tctl", "Tdie", "Package id 0", ""):
                return int(entrada.read_text()) / 1000
    return None


# ---------- placa de vídeo ----------

def gpu() -> dict | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        saida = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3).stdout
        nome, uso, temp, usada, total = [x.strip() for x in saida.splitlines()[0].split(",")]
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None
    return {"nome": nome.replace("NVIDIA ", "").replace("GeForce ", ""), "uso": float(uso), "temp": float(temp),
            "memoria_usada": round(float(usada) / 1024, 1), "memoria_total": round(float(total) / 1024, 1)}


# ---------- memória ----------

def ram() -> dict:
    """Como o `free`: em uso = total − livre − cache. Cache é o que o Linux solta se precisar."""
    m = {}
    for linha in Path("/proc/meminfo").read_text().splitlines():
        chave, valor = linha.split(":", 1)
        m[chave] = int(valor.split()[0]) * 1024
    cache = m["Buffers"] + m["Cached"] + m.get("SReclaimable", 0)
    livre = m["MemFree"]
    total = m["MemTotal"]
    return {"total": total / GIB, "usada": (total - livre - cache) / GIB, "cache": cache / GIB,
            "livre": livre / GIB, "disponivel": m["MemAvailable"] / GIB}


# ---------- discos ----------

def _disco_de(dispositivo: str) -> str:
    """/dev/sdb2 → sdb ; /dev/nvme0n1p1 → nvme0n1."""
    nome = Path(os.path.realpath(dispositivo)).name
    pai = Path(f"/sys/class/block/{nome}/..").resolve().name
    return pai if Path(f"/sys/block/{pai}").exists() else nome


def _ler(caminho: Path, padrao: str = "") -> str:
    try:
        return caminho.read_text().strip()
    except OSError:
        return padrao


def discos() -> list[dict]:
    vistos, lista = set(), []
    for linha in Path("/proc/mounts").read_text().splitlines():
        dispositivo, ponto, tipo = linha.split()[:3]
        if not dispositivo.startswith("/dev/") or dispositivo.startswith("/dev/loop"):
            continue
        ponto = ponto.replace("\\040", " ")
        if dispositivo in vistos:
            continue
        try:
            st = os.statvfs(ponto)
        except OSError:
            continue
        total_bruto = st.f_blocks * st.f_frsize
        if total_bruto < MINIMO:
            continue
        vistos.add(dispositivo)
        livre = st.f_bavail * st.f_frsize
        usado = (st.f_blocks - st.f_bfree) * st.f_frsize
        disco = _disco_de(dispositivo)
        bloco = Path("/sys/block") / disco
        girando = _ler(bloco / "queue/rotational", "0") == "1"
        tamanho = int(_ler(bloco / "size", "0") or 0) * 512 / 1e9   # o tamanho "da caixa" (GB decimais)
        modelo = _ler(bloco / "device/model").split()
        lista.append({
            "tipo": "HD" if girando else "SSD",
            "ponto": ponto,
            "modelo": modelo[0].capitalize() if modelo else disco,
            "tamanho": round(tamanho),
            "papel": PAPEIS.get(ponto, ""),
            # Como o df: o usado sobre o que dá para usar (sem a reserva do sistema).
            "total": (usado + livre) / GIB,
            "usado": usado / GIB,
            "livre": livre / GIB,
            "pct": 100 * usado / (usado + livre) if usado + livre else 0.0,
        })
    # O do sistema primeiro, depois os outros SSDs, depois os HDs.
    lista.sort(key=lambda d: (d["ponto"] != "/", d["tipo"] == "HD", d["ponto"]))
    # Dois do mesmo tipo: o rótulo leva o modelo para diferenciar.
    for d in lista:
        if sum(1 for o in lista if o["tipo"] == d["tipo"]) > 1:
            d["titulo"] = f'{d["tipo"]} {d["modelo"]}'
        else:
            d["titulo"] = d["tipo"]
    return lista


# ---------- tudo junto ----------

class Monitor:
    def __init__(self) -> None:
        self.cpu = Processador()

    def ler(self) -> dict:
        return {"hora": time.time(), "gpu": gpu(),
                "cpu": {"nome": self.cpu.nome, "nucleos": self.cpu.nucleos, "uso": self.cpu.uso(), "temp": temp_cpu()},
                "ram": ram(), "discos": discos()}
