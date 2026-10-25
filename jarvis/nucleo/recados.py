"""O relógio interno do Jarvis: recados que ele deixa para si mesmo (25/10/2026).

O Claude não tem relógio: só existe enquanto responde uma mensagem. Para
"lembra a Karyn que segunda tem o CIEE" (ou "me avisa daqui a 20 minutos"),
o próprio Jarvis anota um recado com dia e hora num arquivo de texto da casa
dele, com as ferramentas de arquivo de sempre:

    - 2026-10-26 07:30 | lembrar a Karyn do CIEE no grupo

e o corpo confere os recados a cada volta, sem gastar nada do Claude. Na
hora, o recado volta para o cérebro como uma mensagem, e ele faz do jeito
dele. Não é uma ferramenta de lembrete: é o Jarvis ter noção de tempo.

Python puro, sem agendador do sistema (systemd, cron, Agendador de Tarefas):
o mesmo funciona no Windows (decisão do Léo: o Jarvis não pode depender deste
PC).
"""

from __future__ import annotations

import datetime as dt
import re
import threading
from pathlib import Path

NOME = "recados.md"
_LINHA = re.compile(r"^\s*[-*]?\s*(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})\s*[|—-]\s*(.+?)\s*$")
_trava = threading.Lock()

COMO_USAR = (
    "Para fazer algo numa hora marcada (lembrar alguém, avisar, conferir algo depois), "
    f"anote um recado no arquivo `{NOME}` da sua pasta, uma linha por recado, no formato "
    "`- AAAA-MM-DD HH:MM | o que fazer` (ex.: `- 2026-10-26 07:30 | lembrar a Karyn do CIEE no grupo`). "
    "Na hora, o recado volta para você como uma mensagem e você faz o que anotou. "
    "Para desmarcar, apague a linha."
)


def vencidos(arquivo: Path, agora: dt.datetime | None = None) -> list[str]:
    """Tira do arquivo os recados cuja hora já chegou e devolve "HH:MM — texto".
    O resto do arquivo (outros recados, anotações soltas) fica como está."""
    if not arquivo.is_file():
        return []
    agora = agora or dt.datetime.now()
    with _trava:
        try:
            linhas = arquivo.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            return []
        saida, ficam = [], []
        for linha in linhas:
            m = _LINHA.match(linha)
            if m:
                try:
                    quando = dt.datetime.fromisoformat(f"{m[1]} {int(m[2]):02d}:{m[3]}")
                except ValueError:
                    ficam.append(linha)
                    continue
                if quando <= agora:
                    saida.append(f"{quando:%d/%m %H:%M} — {m[4]}")
                    continue
            ficam.append(linha)
        if saida:
            arquivo.write_text("\n".join(ficam) + ("\n" if ficam else ""), encoding="utf-8")
        return saida
