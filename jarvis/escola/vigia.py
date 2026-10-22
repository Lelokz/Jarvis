"""A vigia da escola, dentro do Jarvis: lê 3 vezes por dia e segura a sessão.

Cada leitura é um processo à parte (`python -m jarvis.escola`), em nice 19:
o navegador escondido não divide memória nem pausa com o laço de áudio.
O que for novo o próprio processo notifica no PC e guarda em novidades.jsonl,
que o celular busca na porta remota (/novidades).
"""

from __future__ import annotations

import datetime as dt
import json
import os
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

    def _rodar(self, comando: str) -> None:
        try:
            subprocess.run([sys.executable, "-m", "jarvis.escola", comando], cwd=RAIZ,
                           capture_output=True, timeout=900, preexec_fn=lambda: os.nice(19))
        except Exception:
            pass  # falhou desta vez: tenta no próximo horário

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
