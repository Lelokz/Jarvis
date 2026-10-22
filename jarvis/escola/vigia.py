"""A vigia da escola, dentro do Jarvis: lê 3 vezes por dia e segura a sessão.

Cada leitura é um processo à parte (`python -m jarvis.escola`), em nice 19:
o navegador escondido não divide memória nem pausa com o laço de áudio.
O que for novo fica numa fila; o laço principal pega com `pegar()` e manda
para o celular. A notificação do PC o próprio processo já mostra.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import queue
import subprocess
import sys
import threading
import time

from jarvis.config import RAIZ

from .__main__ import RESUMO

HORAS_DE_LER = (7, 12, 18)
MANTER_A_CADA_S = 10 * 60
# De noite não roda nada (o Léo dorme e o PC fica quieto).
NOITE = (23, 7)


def _noite(agora: dt.datetime) -> bool:
    return agora.hour >= NOITE[0] or agora.hour < NOITE[1]


def _ultima_leitura() -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(json.loads(RESUMO.read_text(encoding="utf-8"))["lido_em"])
    except (OSError, ValueError, KeyError):
        return None


class Vigia(threading.Thread):
    def __init__(self) -> None:
        super().__init__(name="vigia-escola", daemon=True)
        self._fila: queue.Queue[str] = queue.Queue()

    def pegar(self) -> str | None:
        try:
            return self._fila.get_nowait()
        except queue.Empty:
            return None

    def _rodar(self, comando: str) -> None:
        try:
            saida = subprocess.run([sys.executable, "-m", "jarvis.escola", comando], cwd=RAIZ,
                                   capture_output=True, text=True, timeout=900,
                                   preexec_fn=lambda: os.nice(19))
            novas = json.loads(saida.stdout.strip().splitlines()[-1])["novidades"]
        except Exception:
            return  # falhou desta vez: tenta no próximo horário
        if novas:
            self._fila.put("\n".join(novas))

    def _devia_ler(self, agora: dt.datetime) -> bool:
        ultima = _ultima_leitura()
        if ultima is None:
            return True
        ultimo_horario = max((agora.replace(hour=h, minute=0, second=0, microsecond=0)
                              for h in HORAS_DE_LER if h <= agora.hour), default=None)
        if ultimo_horario is None:  # antes das 7h: vale o das 18h de ontem
            ultimo_horario = (agora - dt.timedelta(days=1)).replace(hour=HORAS_DE_LER[-1], minute=0,
                                                                   second=0, microsecond=0)
        return ultima < ultimo_horario

    def run(self) -> None:
        time.sleep(60)  # deixa o Jarvis terminar de ligar
        ultimo_manter = time.monotonic()
        while True:
            agora = dt.datetime.now()
            if not _noite(agora):
                if self._devia_ler(agora):
                    self._rodar("ler")
                    ultimo_manter = time.monotonic()
                elif time.monotonic() - ultimo_manter >= MANTER_A_CADA_S:
                    self._rodar("manter")
                    ultimo_manter = time.monotonic()
            time.sleep(60)
