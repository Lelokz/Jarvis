"""Google Agenda: criar evento e ver o que tem no dia.

**Esta é a primeira coisa do projeto que sai da máquina.** Tudo até aqui era
local; aqui há rede, credencial e uma conta de verdade — errar escreve na
agenda que o celular do Léo mostra. Por isso o módulo é conservador: falha
dizendo o que houve, e nunca apaga nada.

**Apagar está fora da Etapa 4** de propósito: é ação destrutiva, a §2.3 exige
confirmação falada, e o resto tem que estar de pé antes.

**É a fundação de Drive e Fotos.** Os três usam o mesmo projeto no Google Cloud
e o mesmo login; quando entrarem, cada um custa só mais um escopo declarado e
uma reautorização — não um sistema de autenticação novo. É por isso que a
autenticação vive aqui separada das operações.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

ESCOPOS = ["https://www.googleapis.com/auth/calendar.events"]


@dataclass(frozen=True)
class Evento:
    titulo: str
    inicio: dt.datetime
    dia_inteiro: bool = False

    @property
    def hora_falavel(self) -> str:
        if self.dia_inteiro:
            return "o dia todo"
        if self.inicio.minute:
            return f"{self.inicio.hour}h{self.inicio.minute:02d}"
        return f"{self.inicio.hour}h"


@dataclass(frozen=True)
class Resultado:
    ok: bool
    mensagem: str
    detalhe: dict | None = None


class ErroDaAgenda(RuntimeError):
    """Falha com instrução de como resolver — nunca stack trace cru."""


class Agenda:
    def __init__(self, cfg, raiz: Path) -> None:
        self.cfg = cfg
        self.credenciais = raiz / "credenciais_google.json"
        self.token = raiz / "token_google.json"
        self._servico = None

    # -- autenticação ------------------------------------------------------

    def _conectar(self):
        """Carrega o token e renova sozinho quando vencido.

        O app ficou em modo "Testing" no console do Google, porque publicar
        exige URL de página inicial e de política de privacidade que o Jarvis
        não tem. Nesse modo **a autorização expira em 7 dias** — quando isso
        acontecer, a renovação falha e a saída é rodar `autorizar_google.py`
        de novo. A mensagem abaixo diz isso em vez de estourar um erro do
        Google que ninguém entende.
        """
        if self._servico is not None:
            return self._servico

        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        if not self.token.is_file():
            raise ErroDaAgenda(
                "A agenda ainda não foi autorizada.\n"
                "  Rode:  ./.venv/bin/python autorizar_google.py"
            )

        credencial = Credentials.from_authorized_user_file(str(self.token), ESCOPOS)
        if not credencial.valid:
            if credencial.expired and credencial.refresh_token:
                try:
                    credencial.refresh(Request())
                    self.token.write_text(credencial.to_json(), encoding="utf-8")
                except Exception as e:
                    raise ErroDaAgenda(
                        f"A autorização do Google expirou ({e}).\n"
                        "  Isto é esperado: o app está em modo Testing, e nele\n"
                        "  o Google derruba a autorização a cada 7 dias.\n"
                        "  Rode:  ./.venv/bin/python autorizar_google.py"
                    ) from e
            else:
                raise ErroDaAgenda(
                    "A autorização do Google não serve mais.\n"
                    "  Rode:  ./.venv/bin/python autorizar_google.py"
                )

        self._servico = build(
            "calendar", "v3", credentials=credencial, cache_discovery=False
        )
        return self._servico

    def conferir(self) -> dict:
        """Prova o acesso e diz QUAL conta está ligada.

        Feito com `events().list()` de propósito. A checagem anterior usava
        `calendars().get()`, que lê metadados do calendário e **não cabe no
        escopo** `calendar.events` — estourava 403 "insufficient authentication
        scopes". Ampliar o escopo resolveria e seria a saída errada: o escopo
        estreito é decisão deliberada.

        O `events().list()` devolve, de graça e dentro do escopo, o email da
        conta em `summary`, o fuso do calendário e o papel do usuário. O campo
        `account` do token fica vazio, então não serviria para isto.
        """
        r = (
            self._conectar()
            .events()
            .list(calendarId="primary", maxResults=1)
            .execute()
        )
        return {
            "conta": r.get("summary", "?"),
            "fuso": r.get("timeZone", "?"),
            "papel": r.get("accessRole", "?"),
        }

    # -- operações ---------------------------------------------------------

    def criar(self, titulo: str, inicio: dt.datetime) -> Resultado:
        fim = inicio + dt.timedelta(minutes=self.cfg.duracao_padrao_min)
        corpo = {
            "summary": titulo,
            "start": {"dateTime": inicio.isoformat(), "timeZone": self.cfg.fuso},
            "end": {"dateTime": fim.isoformat(), "timeZone": self.cfg.fuso},
        }
        try:
            criado = (
                self._conectar()
                .events()
                .insert(calendarId="primary", body=corpo)
                .execute()
            )
        except ErroDaAgenda:
            raise
        except Exception as e:
            return Resultado(False, f"Não consegui criar o evento: {e}")
        return Resultado(
            True, "Marquei.", {"id": criado.get("id"), "link": criado.get("htmlLink")}
        )

    def do_dia(self, dia: dt.date) -> list[Evento]:
        inicio = dt.datetime.combine(dia, dt.time.min)
        fim = dt.datetime.combine(dia, dt.time.max)
        try:
            resposta = (
                self._conectar()
                .events()
                .list(
                    calendarId="primary",
                    timeMin=inicio.astimezone().isoformat(),
                    timeMax=fim.astimezone().isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=50,
                )
                .execute()
            )
        except ErroDaAgenda:
            raise
        except Exception as e:
            raise ErroDaAgenda(f"Não consegui ler a agenda: {e}") from e

        eventos = []
        for item in resposta.get("items", []):
            comeco = item.get("start", {})
            if "dateTime" in comeco:
                quando = dt.datetime.fromisoformat(comeco["dateTime"])
                dia_inteiro = False
            elif "date" in comeco:
                quando = dt.datetime.fromisoformat(comeco["date"] + "T00:00:00")
                dia_inteiro = True
            else:
                continue
            eventos.append(
                Evento(
                    titulo=item.get("summary", "sem título"),
                    inicio=quando.replace(tzinfo=None),
                    dia_inteiro=dia_inteiro,
                )
            )
        return eventos
