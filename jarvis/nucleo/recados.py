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
import hashlib
import json
import re
import threading
from pathlib import Path

NOME = "recados.md"
_LINHA = re.compile(r"^\s*[-*]?\s*(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})\s*[|—-]\s*(.+?)\s*$")
_trava = threading.Lock()


def como_usar(arquivo: str = NOME) -> str:
    """A explicação para as instruções do Claude (o arquivo muda: no grupo, os
    recados ficam dentro da memória do grupo)."""
    return ("Para fazer algo numa hora marcada (lembrar alguém, avisar, conferir algo depois), "
            f"anote um recado no arquivo `{arquivo}` da sua pasta, uma linha por recado, no formato "
            "`- AAAA-MM-DD HH:MM | o que fazer` (ex.: `- 2026-10-26 07:30 | lembrar a Karyn do CIEE no grupo`). "
            "Na hora, o recado volta para você como uma mensagem e você faz o que anotou. "
            "Para REPETIR: `- todo dia 07:00 | o que fazer` ou `- toda seg 07:30 | o que fazer` "
            "(dias: dom, seg, ter, qua, qui, sex, sab; dá pra juntar: `- toda seg qua sex 18:00 | ...`). "
            "Para desmarcar, apague a linha.")


COMO_USAR = como_usar()


# Os que repetem (etapa 5 do tchan, 11/11/2026): "- todo dia 07:00 | ..." ou
# "- toda seg qua 18:00 | ...". Ficam no arquivo; o que já tocou fica anotado
# ao lado (recados-tocados.json), e cada vez toca uma só, até 2 h depois da
# hora (a NOVA desligada na hora: toca quando ligar, se ainda der).
_REPETE = re.compile(r"^\s*[-*]?\s*(?:todo dia|todos os dias|toda|todo)\s*(?P<dias>(?:(?:dom|seg|ter|qua|qui|sex|sab|sáb)\w*[\s,e]*)*)"
                     r"\s*(?P<h>\d{1,2}):(?P<m>\d{2})\s*[|—-]\s*(?P<texto>.+?)\s*$", re.IGNORECASE)
_DIAS = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]   # datetime.weekday()
_NOMES = {"seg": "segunda", "ter": "terça", "qua": "quarta", "qui": "quinta", "sex": "sexta", "sab": "sábado", "dom": "domingo"}
TOLERANCIA = dt.timedelta(hours=2)


def _dias_da_linha(texto: str) -> list[int]:
    achados = re.findall(r"(dom|seg|ter|qua|qui|sex|sab|sáb)", texto.lower())
    return sorted({_DIAS.index("sab" if d == "sáb" else d) for d in achados}) or list(range(7))


def _repete(linha: str):
    m = _REPETE.match(linha)
    if not m or not (0 <= int(m["h"]) < 24 and 0 <= int(m["m"]) < 60):
        return None
    return _dias_da_linha(m["dias"] or ""), int(m["h"]), int(m["m"]), m["texto"]


def _ultima_vez(dias: list[int], h: int, mi: int, agora: dt.datetime) -> dt.datetime:
    for atras in range(8):
        d = (agora - dt.timedelta(days=atras)).replace(hour=h, minute=mi, second=0, microsecond=0)
        if d.weekday() in dias and d <= agora:
            return d
    return agora - dt.timedelta(days=8)


def _proxima_vez(dias: list[int], h: int, mi: int, agora: dt.datetime) -> dt.datetime:
    for frente in range(8):
        d = (agora + dt.timedelta(days=frente)).replace(hour=h, minute=mi, second=0, microsecond=0)
        if d.weekday() in dias and d > agora:
            return d
    return agora


def _nome_da_repeticao(dias: list[int]) -> str:
    if len(dias) == 7:
        return "todo dia"
    if dias == [0, 1, 2, 3, 4]:
        return "dia de semana"
    if len(dias) == 1:
        d = _DIAS[dias[0]]
        return ("todo " if d in ("sab", "dom") else "toda ") + _NOMES[d]
    return "toda " + ", ".join(_DIAS[d] for d in dias)


def _id(linha: str) -> str:
    return hashlib.sha1(linha.strip().encode("utf-8")).hexdigest()[:10]


def _tocados(arquivo: Path) -> Path:
    return arquivo.with_name("recados-tocados.json")


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
        # Os que repetem: ficam no arquivo; tocam uma vez por vez.
        try:
            tocados = json.loads(_tocados(arquivo).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            tocados = {}
        mudou = False
        for linha in ficam:
            r = _repete(linha)
            if r is None:
                continue
            dias, h, mi, texto = r
            vez = _ultima_vez(dias, h, mi, agora)
            chave = _id(linha)
            if agora - vez <= TOLERANCIA and tocados.get(chave, "") < vez.isoformat():
                saida.append(f"{vez:%d/%m %H:%M} — {texto}")
                tocados[chave] = vez.isoformat()
                mudou = True
        if mudou:
            _tocados(arquivo).write_text(json.dumps(tocados), encoding="utf-8")
        return saida


def listar(arquivo: Path, agora: dt.datetime | None = None) -> list[dict]:
    """Os recados pra tela "Agendados": [{id, texto, quando (época), repete}],
    do mais perto pro mais longe. repete = "" (uma vez), "todo dia", "toda segunda"…"""
    agora = agora or dt.datetime.now()
    try:
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    saida = []
    for linha in linhas:
        m = _LINHA.match(linha)
        if m:
            try:
                quando = dt.datetime.fromisoformat(f"{m[1]} {int(m[2]):02d}:{m[3]}")
            except ValueError:
                continue
            saida.append({"id": _id(linha), "texto": m[4], "quando": quando.timestamp(), "repete": ""})
            continue
        r = _repete(linha)
        if r:
            dias, h, mi, texto = r
            saida.append({"id": _id(linha), "texto": texto, "quando": _proxima_vez(dias, h, mi, agora).timestamp(),
                          "repete": _nome_da_repeticao(dias)})
    return sorted(saida, key=lambda x: x["quando"])


def apagar(arquivo: Path, ident: str) -> bool:
    """A lixeira da tela "Agendados": tira a linha do recado."""
    with _trava:
        try:
            linhas = arquivo.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            return False
        ficam = [l for l in linhas if not ((_LINHA.match(l) or _repete(l)) and _id(l) == ident)]
        if len(ficam) == len(linhas):
            return False
        arquivo.write_text("\n".join(ficam) + ("\n" if ficam else ""), encoding="utf-8")
        return True
