"""O que dá para abrir, descoberto no próprio PC — sem precisar de atalho.

Três fontes que o sistema já mantém sozinho:

- **programas instalados**: os `.desktop` do menu (os mesmos ícones que o
  Mint mostra), inclusive Flatpak;
- **projetos do VS Code**: toda pasta já aberta nele deixa um
  `workspace.json` em `~/.config/Code/User/workspaceStorage/`;
- **favoritos do Brave**: o nome vem do endereço (`kabum.com.br` → "kabum"),
  porque os favoritos da barra costumam ser só ícone, sem nome.

Nada disto vai para o git: é lido do PC de quem está usando. É o que deixa o
Jarvis ir para outra pessoa sem levar as coisas do Léo, e o que dispensa
cadastrar no `atalhos.toml` o que o sistema já sabe.

O `atalhos.toml` continua valendo e **ganha** de qualquer coisa daqui com o
mesmo nome: é o Léo dizendo explicitamente o que quer.
"""

from __future__ import annotations

import configparser
import json
import os
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from .atalhos import Atalho, normalizar

_PASTAS_DE_APPS = [
    Path("/usr/share/applications"),
    Path("~/.local/share/applications").expanduser(),
    Path("/var/lib/flatpak/exports/share/applications"),
    Path("~/.local/share/flatpak/exports/share/applications").expanduser(),
    Path("/var/lib/snapd/desktop/applications"),
]
_VSCODE = Path("~/.config/Code/User/workspaceStorage").expanduser()
_BRAVE = Path("~/.config/BraveSoftware/Brave-Browser/Default/Bookmarks").expanduser()

# Os próprios ícones do Jarvis: "abre o Jarvis" não deve relançar a si mesmo,
# e "desligar Jarvis" por voz seria um desligar sem querer.
_IGNORAR_APPS = {"jarvis", "desligar jarvis"}

# Como as pessoas chamam alguns programas, pelo nome do arquivo .desktop.
_APELIDOS_EXTRA = {
    "code": ("vs code", "vscode"),
    "brave-browser": ("brave", "navegador"),
    "org.gnome.SystemMonitor": ("monitor do sistema", "gerenciador de tarefas"),
    "gnome-system-monitor": ("monitor do sistema", "gerenciador de tarefas"),
    "org.gnome.Calculator": ("calculadora",),
    "org.gnome.Terminal": ("terminal",),
    "com.rtosta.zapzap": ("whatsapp", "zap"),
}

# Pedaços de endereço que não são o nome do site.
_RUIDO_DOMINIO = {"www", "m", "br", "pt", "en", "com", "net", "org", "io",
                  "co", "gov", "edu", "app", "ai", "is", "me", "tv", "gg"}


def _apps() -> list[Atalho]:
    vistos: set[str] = set()
    achados: list[Atalho] = []
    for pasta in _PASTAS_DE_APPS:
        if not pasta.is_dir():
            continue
        for arq in sorted(pasta.glob("*.desktop")):
            ini = configparser.RawConfigParser(strict=False, interpolation=None)
            try:
                ini.read(arq, encoding="utf-8")
            except (configparser.Error, UnicodeDecodeError):
                continue
            if not ini.has_section("Desktop Entry"):
                continue
            s = ini["Desktop Entry"]
            if (s.get("Type") != "Application"
                    or s.get("NoDisplay", "false").lower() == "true"
                    or s.get("Hidden", "false").lower() == "true"):
                continue
            nome = (s.get("Name[pt_BR]") or s.get("Name") or "").strip()
            if not nome or normalizar(nome) in _IGNORAR_APPS or normalizar(nome) in vistos:
                continue
            vistos.add(normalizar(nome))
            # Apelidos: o nome em inglês e o do arquivo ("com.discordapp.Discord"
            # → "discord", "code" → "code"). É como as pessoas chamam.
            apelidos = {s.get("Name", "").strip(), arq.stem.split(".")[-1].replace("-", " ")}
            apelidos |= set(_APELIDOS_EXTRA.get(arq.stem, ()))
            apelidos = tuple(a for a in apelidos if a and normalizar(a) != normalizar(nome))
            achados.append(Atalho(nome, "app", str(arq), apelidos=apelidos, origem="sistema"))
    return achados


def _projetos_vscode() -> list[Atalho]:
    pastas: set[str] = set()
    for arq in _VSCODE.glob("*/workspace.json"):
        try:
            uri = json.loads(arq.read_text(encoding="utf-8")).get("folder", "")
        except (OSError, ValueError):
            continue
        if uri.startswith("file://"):
            caminho = unquote(urlparse(uri).path)
            if os.path.isdir(caminho):
                pastas.add(caminho)
    achados = []
    for caminho in sorted(pastas):
        nome = Path(caminho).name.replace("-", " ").replace("_", " ")
        achados.append(Atalho(f"projeto {nome}", "vscode", caminho, origem="sistema"))
    return achados


def nome_do_site(url: str) -> str:
    """`https://music.youtube.com/` → "youtube music"; `kabum.com.br` → "kabum"."""
    partes = [p for p in (urlparse(url).hostname or "").split(".")
              if p and p not in _RUIDO_DOMINIO]
    if not partes:
        return ""
    # O nome principal é o último pedaço que sobrou; o que vem antes é
    # subdomínio e entra depois ("music.youtube" → "youtube music").
    return " ".join([partes[-1], *partes[:-1]])


def _favoritos_brave() -> list[Atalho]:
    try:
        raiz = json.loads(_BRAVE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    achados: list[Atalho] = []
    vistos: set[str] = set()

    def andar(no: dict) -> None:
        if no.get("type") == "url":
            url = no.get("url", "")
            nome = nome_do_site(url)
            if nome and url.startswith(("http://", "https://")) and nome not in vistos:
                vistos.add(nome)
                titulo = (no.get("name") or "").strip()
                apelidos = (titulo,) if titulo and normalizar(titulo) != normalizar(nome) else ()
                achados.append(Atalho(nome, "site", url, apelidos=apelidos, origem="sistema"))
        for filho in no.get("children", []):
            andar(filho)

    for no in raiz.get("roots", {}).values():
        if isinstance(no, dict):
            andar(no)
    return achados


def descobrir() -> list[Atalho]:
    return _apps() + _projetos_vscode() + _favoritos_brave()


class Catalogo:
    """Lê de novo a cada poucos minutos: programa instalado ou favorito novo
    entra sem reiniciar o Jarvis. Ler tudo custa poucas dezenas de ms."""

    VALIDADE_S = 300.0

    def __init__(self) -> None:
        self._itens: list[Atalho] = []
        self._lido_em = -1e9

    def itens(self) -> list[Atalho]:
        if time.monotonic() - self._lido_em > self.VALIDADE_S:
            self._itens = descobrir()
            self._lido_em = time.monotonic()
        return self._itens
