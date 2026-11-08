"""O alerta falado do Monitor do Sistema (08/11/2026): o Jarvis avisa quando
alguma peça passa do limite, sem gastar nada do Claude.

Roda numa thread própria (o nvidia-smi demora um pouco e o laço do microfone
não pode esperar) e deixa as falas numa fila; o assistente pega com `pegar()`.

O que avisa (o uso alto sozinho não: jogo é para usar a placa a 100 %):
- placa de vídeo quente: 85 °C ou mais por 30 s;
- processador quente: 90 °C ou mais por 30 s;
- RAM acabando: menos de 1 GB disponível (contando o cache) por 15 s,
  dizendo o programa que mais está comendo;
- disco cheio: passou de 95 % (e de novo se passar de 98 %).
A mesma coisa não repete antes de 30 min; o disco só volta a avisar depois de
descer de 93 %.
"""

from __future__ import annotations

import queue
import threading
import time
from collections import defaultdict
from pathlib import Path

import os

from jarvis.monitor import jogo
from jarvis.monitor.leitura import Monitor

INTERVALO = 5            # segundos entre leituras
REPETIR = 30 * 60        # a mesma coisa não volta antes disto
GPU_QUENTE, CPU_QUENTE = 85, 90
RAM_POUCA = 1.0          # GB disponíveis
DISCO = (95, 98)         # % que avisam
DISCO_REARMA = 93
FIM_DO_JOGO = 30         # segundos sem o jogo até sair do modo jogo (reabrir não pisca)


def _num(x: float) -> str:
    return str(round(x)).replace(".", ",")


def maior_programa() -> str | None:
    """O nome do programa que mais ocupa RAM (somando as janelas/abas dele)."""
    soma: dict[str, int] = defaultdict(int)
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            nome, rss = "", 0
            for linha in (p / "status").read_text().splitlines():
                if linha.startswith("Name:"):
                    nome = linha.split(":", 1)[1].strip()
                elif linha.startswith("VmRSS:"):
                    rss = int(linha.split()[1])
                    break
        except (OSError, ValueError):
            continue
        if nome.startswith("python"):
            nome = _python(p) or nome
        if nome:
            soma[nome] += rss
    if not soma:
        return None
    nome = max(soma, key=soma.get)
    # Nomes que o Léo reconhece.
    return {"brave": "o Brave", "java": "o Minecraft", "Godot_v4": "o Godot", "godot": "o Godot",
            "code": "o VS Code", "obs": "o OBS", "python": "um programa em Python",
            "python3": "um programa em Python", "Web Content": "o navegador",
            "assistente": "o próprio Jarvis", "interface": "a janela do Jarvis",
            "servidor_rvc": "a voz do Jarvis", "servidor_friday": "a voz da Friday",
            "servidor_voz": "a voz do Jarvis"}.get(nome, nome)


def _python(p: Path) -> str | None:
    """Um Python não diz nada: o nome certo é o do script que ele roda."""
    try:
        partes = (p / "cmdline").read_bytes().split(b"\0")
    except OSError:
        return None
    for parte in partes[1:]:
        texto = parte.decode(errors="ignore")
        if texto.endswith(".py"):
            return Path(texto).stem
        if texto.startswith("jarvis."):
            return texto
    return None


class Vigia(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True, name="vigia-do-monitor")
        self._fila: queue.Queue[str] = queue.Queue()
        self._monitor = Monitor()
        self._desde: dict[str, float] = {}        # há quanto tempo a condição está ligada
        self._avisado: dict[str, float] = {}      # quando avisou por último
        self._disco_nivel: dict[str, int] = {}    # 0, 95 ou 98 já avisados por disco
        # O modo jogo: o nome do jogo aberto (None = não está jogando). O aviso de
        # disco cheio espera o jogo fechar; os de calor e RAM não (é jogando que importam).
        self.jogo: str | None = None
        self._jogo_visto = 0.0
        self._disco_guardado: list[str] = []

    def pegar(self) -> str | None:
        try:
            return self._fila.get_nowait()
        except queue.Empty:
            return None

    def run(self) -> None:
        while True:
            time.sleep(INTERVALO)
            try:
                self._olhar_jogo(time.monotonic())
                for fala in self.conferir(self._monitor.ler(), time.monotonic()):
                    self._fila.put(fala)
            except Exception:
                pass   # uma leitura que falhou não derruba a vigia

    def _olhar_jogo(self, agora: float) -> None:
        nome = jogo.jogando()
        if nome:
            self._jogo_visto = agora
            self.jogo = nome
            # Toda volta: o que o Jarvis abrir no meio do jogo também vai pros núcleos leves.
            jogo.aliviar(os.getpid(), True)
        elif self.jogo and agora - self._jogo_visto >= FIM_DO_JOGO:
            self.jogo = None
            jogo.aliviar(os.getpid(), False)
            for fala in self._disco_guardado:
                self._fila.put(fala)
            self._disco_guardado = []

    # Separado do run para dar para testar com números inventados.
    def conferir(self, d: dict, agora: float) -> list[str]:
        falas = []

        def sustentado(chave: str, ligado: bool, segundos: float) -> bool:
            if not ligado:
                self._desde.pop(chave, None)
                return False
            inicio = self._desde.setdefault(chave, agora)
            if agora - inicio < segundos:
                return False
            if agora - self._avisado.get(chave, -REPETIR) < REPETIR:
                return False
            self._avisado[chave] = agora
            return True

        g = d.get("gpu")
        if g and sustentado("gpu", g["temp"] >= GPU_QUENTE, 30):
            falas.append(f'A placa de vídeo está a {_num(g["temp"])} graus. Está esquentando demais.')
        c = d["cpu"]
        if c["temp"] is not None and sustentado("cpu", c["temp"] >= CPU_QUENTE, 30):
            falas.append(f'O processador está a {_num(c["temp"])} graus. Está esquentando demais.')
        r = d["ram"]
        if sustentado("ram", r["disponivel"] < RAM_POUCA, 15):
            quem = maior_programa()
            extra = f" Quem mais está usando é {quem}." if quem else ""
            falas.append(f"A memória RAM está acabando: sobrou menos de um giga.{extra}")
        for k in d["discos"]:
            ponto, pct = k["ponto"], k["pct"]
            ja = self._disco_nivel.get(ponto, 0)
            if pct < DISCO_REARMA:
                self._disco_nivel[ponto] = 0
                continue
            passou = max((n for n in DISCO if pct >= n), default=0)
            if passou > ja:
                self._disco_nivel[ponto] = passou
                nome = "O SSD" if k["tipo"] == "SSD" else "O HD"
                if k["titulo"] not in ("SSD", "HD"):
                    nome = "O " + k["titulo"]
                livre = k["livre"]
                sobra = f"{_num(livre)} gigas" if livre >= 1.5 else "menos de dois gigas"
                fala = f"{nome} passou de {passou} por cento: só sobraram {sobra} livres."
                if self.jogo:
                    self._disco_guardado.append(fala)
                else:
                    falas.append(fala)
        return falas
