"""O estado das conexões, para a aba Conexões dos Ajustes (janela e app).

Cada conexão vira {id, estado, detalhe}: "conectado" (funcionando agora),
"pronto" (configurado, esperando: o relógio só aparece quando está aberto) ou
"desligado". Tudo aqui é olhada rápida e local (roda na thread de áudio, junto
com o evento "ajustes"): nada de rede de fora, e o único programa chamado (o
Tailscale) tem teto de 1 s.
O nome e a descrição de cada uma ficam na tela, não aqui.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import urlparse

from jarvis.config import Config

RAIZ = Path(__file__).resolve().parent.parent


def _porta_aberta(url: str) -> bool:
    """A ponte do WhatsApp responde (só conecta na porta local; não manda nada)."""
    u = urlparse(url)
    try:
        with socket.create_connection((u.hostname or "127.0.0.1", u.port or 80), timeout=0.3):
            return True
    except OSError:
        return False


def _tailscale() -> bool:
    """O Tailscale de pé. Aqui ele roda sem interface de rede (userspace), então
    pergunta ao próprio (~30 ms; com teto de 1 s)."""
    exe = shutil.which("tailscale") or str(Path.home() / ".local/bin/tailscale")
    try:
        r = subprocess.run([exe, "status", "--json", "--peers=false"], capture_output=True, timeout=1)
        return json.loads(r.stdout or b"{}").get("BackendState") == "Running"
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False


def _atalhos() -> int:
    try:
        return len(tomllib.loads((RAIZ / "atalhos.toml").read_text(encoding="utf-8")))
    except (OSError, tomllib.TOMLDecodeError):
        return 0


def estado(cfg: Config, ajustes: dict, conectados: set[str], tem_escola: bool) -> list[dict]:
    """`conectados`: quem está na ponte agora ("celular-app", "relogio"...)."""
    def item(id_: str, estado_: str, detalhe: str = "") -> dict:
        return {"id": id_, "estado": estado_, "detalhe": detalhe}

    # A ponte instalada (o banco dela existe) E respondendo: só a porta aberta
    # podia ser outro programa.
    whats = cfg.whatsapp.ativo and Path(cfg.whatsapp.banco).expanduser().is_file() \
        and _porta_aberta(cfg.whatsapp.api)
    fora = _tailscale()
    remoto = cfg.remoto.ligada and fora
    n = _atalhos()
    return [
        item("whatsapp", "conectado" if whats else "desligado"),
        item("grupo", "conectado" if ajustes.get("grupo_jid") and ajustes.get("grupo_ligado")
             else "pronto" if ajustes.get("grupo_jid") else "desligado"),
        item("celular", "conectado" if "celular-app" in conectados else "pronto" if remoto else "desligado"),
        item("relogio", "conectado" if "relogio" in conectados else "pronto" if remoto else "desligado"),
        item("fora", "conectado" if fora else "desligado"),
        item("escola", "conectado" if tem_escola else "desligado"),
        item("musica", "conectado" if shutil.which("mpv") else "desligado"),
        item("atalhos", "conectado" if n else "desligado", f"{n} atalhos" if n else ""),
    ]
