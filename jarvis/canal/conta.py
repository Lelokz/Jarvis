"""A ligação com o YouTube do Léo (Painel do Canal, 09/11/2026).

O Léo cria um projeto no Google Cloud (docs/PAINEL - CONECTAR O YOUTUBE.md),
baixa o `cliente.json` (credencial "App para computador") e autoriza uma vez
no navegador. A autorização (token) fica só neste PC, em
~/.local/share/jarvis/canal/, legível só pelo dono. O celular nunca a recebe.
"""

from __future__ import annotations

import os
from pathlib import Path

PASTA = Path(os.environ.get("JARVIS_DADOS", Path.home() / ".local/share/jarvis")) / "canal"
CLIENTE = PASTA / "cliente.json"
TOKEN = PASTA / "token.json"

# force-ssl: ler e editar vídeos, playlists e comentários. Analytics: os números.
ESCOPOS = ["https://www.googleapis.com/auth/youtube.force-ssl",
           "https://www.googleapis.com/auth/yt-analytics.readonly"]


class SemConexao(Exception):
    """Ainda não autorizou (ou a autorização foi revogada)."""


def conectado() -> bool:
    return TOKEN.exists()


def credenciais():
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    if not TOKEN.exists():
        raise SemConexao("o YouTube ainda não foi conectado")
    cred = Credentials.from_authorized_user_file(str(TOKEN), ESCOPOS)
    if not cred.valid:
        try:
            cred.refresh(Request())
        except RefreshError as e:
            raise SemConexao(f"a autorização do YouTube venceu ou foi tirada ({e})") from None
        _guardar(cred)
    return cred


def _guardar(cred) -> None:
    PASTA.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(cred.to_json(), encoding="utf-8")
    TOKEN.chmod(0o600)


def conectar() -> str:
    """Abre o navegador para o Léo autorizar. Uma vez só."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    if not CLIENTE.exists():
        raise SemConexao(f"falta o {CLIENTE.name} em {PASTA} (ver docs/PAINEL - CONECTAR O YOUTUBE.md)")
    fluxo = InstalledAppFlow.from_client_secrets_file(str(CLIENTE), ESCOPOS)
    cred = fluxo.run_local_server(port=0, prompt="consent", access_type="offline",
                                  success_message="Pronto! O Painel do Canal está ligado. Pode fechar esta aba.")
    _guardar(cred)
    return "conectado"


def youtube():
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=credenciais(), cache_discovery=False)


def analytics():
    from googleapiclient.discovery import build
    return build("youtubeAnalytics", "v2", credentials=credenciais(), cache_discovery=False)
