"""O navegador só do Jarvis: um perfil próprio do Chromium, fora do git.

O Léo entra uma vez em cada site (`python -m jarvis.escola.navegador`), com a
janela aberta e sem automação (o Google barra login em navegador
controlado). Depois a leitura usa o mesmo perfil, escondida.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PERFIL = Path.home() / ".local/share/jarvis/escola-navegador"
CHROMIUM = Path.home() / ".cache/ms-playwright/chromium-1247/chrome-linux64/chrome"
KHAN = "https://pt.khanacademy.org/login"
ESTUDANTE = "https://estudanteonline.sed.sc.gov.br/loginweb.aspx"

# O mesmo cofre de senhas que o Playwright usa: sem isso os cookies salvos
# com a janela aberta não abrem na leitura escondida.
ARGS = ["--password-store=basic", "--use-mock-keychain", "--no-first-run",
        "--no-default-browser-check"]


def entrar() -> None:
    PERFIL.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(CHROMIUM), f"--user-data-dir={PERFIL}", *ARGS, KHAN, ESTUDANTE])


if __name__ == "__main__":
    entrar()
    sys.exit(0)
