"""A tela de bloqueio do PC: saber se está bloqueada, bloquear e desbloquear.

Desbloquear não precisa da senha: a sessão é do próprio usuário, e o Linux
deixa ele mesmo destravar. Por isso o Jarvis NUNCA chama `desbloquear()`
direto de um pedido falado: só pelo `desbloqueio.py`, depois do Sim no
celular (decisão do Léo, 23/10/2026: a voz pode ser imitada ou gravada).
"""

from __future__ import annotations

import os
import shutil
import subprocess


def _rodar(*comando: str) -> str:
    try:
        r = subprocess.run(comando, capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _sessao() -> str:
    """O id da sessão gráfica (logind) do usuário."""
    if os.environ.get("XDG_SESSION_ID"):
        return os.environ["XDG_SESSION_ID"]
    usuario = os.environ.get("USER", "")
    for linha in _rodar("loginctl", "list-sessions", "--no-legend").splitlines():
        partes = linha.split()
        if len(partes) >= 3 and partes[2] == usuario:
            tipo = _rodar("loginctl", "show-session", partes[0], "-p", "Type", "--value")
            if tipo in ("x11", "wayland"):
                return partes[0]
    return ""


def bloqueada() -> bool:
    for destino, caminho in (("org.cinnamon.ScreenSaver", "/org/cinnamon/ScreenSaver"),
                             ("org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver")):
        saida = _rodar("gdbus", "call", "--session", "--dest", destino, "--object-path", caminho,
                       "--method", f"{destino}.GetActive")
        if saida:
            return "true" in saida
    sessao = _sessao()
    return bool(sessao) and _rodar("loginctl", "show-session", sessao, "-p", "LockedHint",
                                   "--value") == "yes"


def bloquear() -> None:
    if shutil.which("cinnamon-screensaver-command"):
        subprocess.run(["cinnamon-screensaver-command", "--lock"], timeout=10, check=False)
    else:
        subprocess.run(["loginctl", "lock-session", _sessao()], timeout=10, check=False)


def desbloquear() -> bool:
    """Só pelo desbloqueio.py (o Sim no celular). True se destravou."""
    sessao = _sessao()
    if sessao:
        subprocess.run(["loginctl", "unlock-session", sessao], timeout=10, check=False)
    if shutil.which("cinnamon-screensaver-command") and bloqueada():
        subprocess.run(["cinnamon-screensaver-command", "--deactivate"], timeout=10, check=False)
    return not bloqueada()
