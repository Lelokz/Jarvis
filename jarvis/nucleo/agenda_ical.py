"""Ler a agenda pelo "endereço secreto no formato iCal" do Google.

Existe porque o login do Google (OAuth) cai a cada 7 dias com o app em modo
Testing, e em out/2026 a agenda estava morta havia um mês. O link iCal não
expira e não precisa de login: serve para LER (o que tenho hoje, o briefing).
Criar evento continua pelo OAuth.

O link é secreto — quem tiver vê os eventos — e mora em `agenda_ical.txt`,
fora do git. Eventos que se repetem ("toda terça") saem certos pelo
`recurring_ical_events`.
"""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from .agenda import ErroDaAgenda, Evento

# O Google atualiza o .ics com alguns minutos de atraso; ler de novo a cada
# pergunta só gastaria rede.
_VALIDADE_S = 300


class AgendaIcal:
    def __init__(self, arquivo: Path, fuso: str) -> None:
        self.arquivo = Path(arquivo)
        self.fuso = ZoneInfo(fuso)
        self._cache: tuple[float, bytes] | None = None

    def disponivel(self) -> bool:
        return self.arquivo.is_file() and bool(self.arquivo.read_text().strip())

    def _baixar(self) -> bytes:
        if self._cache and time.monotonic() - self._cache[0] < _VALIDADE_S:
            return self._cache[1]
        url = self.arquivo.read_text().strip()
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
        except requests.RequestException as e:
            raise ErroDaAgenda(f"Não consegui ler a agenda: {e.__class__.__name__}") from e
        self._cache = (time.monotonic(), r.content)
        return r.content

    def entre(self, inicio: dt.datetime, fim: dt.datetime) -> list[Evento]:
        import icalendar
        import recurring_ical_events

        cal = icalendar.Calendar.from_ical(self._baixar())
        eventos = []
        for ev in recurring_ical_events.of(cal).between(inicio, fim):
            comeco = ev.get("DTSTART").dt
            if isinstance(comeco, dt.datetime):
                if comeco.tzinfo is not None:
                    comeco = comeco.astimezone(self.fuso).replace(tzinfo=None)
                dia_inteiro = False
            else:
                comeco = dt.datetime.combine(comeco, dt.time.min)
                dia_inteiro = True
            eventos.append(Evento(titulo=str(ev.get("SUMMARY") or "sem título"),
                                  inicio=comeco, dia_inteiro=dia_inteiro))
        return sorted(eventos, key=lambda e: (not e.dia_inteiro, e.inicio))

    def do_dia(self, dia: dt.date) -> list[Evento]:
        return self.entre(dt.datetime.combine(dia, dt.time.min),
                          dt.datetime.combine(dia, dt.time.max))
