"""A lista fechada de executores. É aqui que a regra §2.1 vira código.

O modelo nunca chega perto deste arquivo. O caminho é:

    modelo → uma string com o nome → busca na tabela → um `tipo` de um
    conjunto fechado → a função correspondente, escrita à mão

Nada do que o modelo diz vira comando. O que ele devolve é chave de busca; o
comando e o alvo vêm do `atalhos.toml`, que é escrito pelo Léo. E a execução é
`subprocess` com lista de argumentos — **nunca** `shell=True`, nunca string
montada. Não existe caminho entre a saída do modelo e um shell.
"""

from __future__ import annotations

import configparser
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .atalhos import Atalho


@dataclass(frozen=True)
class Resultado:
    ok: bool
    mensagem: str  # o que dizer ao Léo
    comando: list[str] | None = None  # para o log da §2.5


@dataclass(frozen=True)
class Comandos:
    """Os executáveis de cada tipo. Vêm da config, não do modelo."""

    site: str = "xdg-open"
    pasta: str = "xdg-open"
    vscode: str = "code"


def _abrir(comando: list[str]) -> None:
    """Dispara e solta.

    `start_new_session` desgruda o processo do Jarvis: fechar o assistente não
    pode fechar o que ele abriu. E a saída vai para o vazio para o navegador
    não despejar log no terminal do ciclo.
    """
    subprocess.Popen(
        comando,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def abrir_caminho(caminho: Path, comandos: Comandos) -> Resultado:
    """Abre um caminho vindo da busca, que não tem `tipo` de tabela.

    Arquivo e pasta vão os dois pelo `xdg-open`: ele respeita o programa padrão
    de cada tipo, que é o que o Léo já configurou no sistema. Adivinhar aqui
    seria pior do que perguntar ao desktop.
    """
    if not caminho.exists():
        return Resultado(False, f"{caminho.name} não está mais lá.")
    executavel = comandos.pasta
    if shutil.which(executavel) is None:
        return Resultado(False, f"O programa {executavel} não está instalado.")
    comando = [executavel, str(caminho)]
    try:
        _abrir(comando)
    except OSError as e:
        return Resultado(False, f"Não consegui abrir {caminho.name}: {e}", comando)
    return Resultado(True, f"Abrindo {caminho.name}.", comando)


# --- programas que sobem só na bandeja -------------------------------------
#
# O ZapZap (e outros) abre do zero escondido: só o ícone na bandeja, sem
# janela. O Léo tinha que abrir de novo para a janela aparecer. Medido: o
# ícone surge ~1,7 s depois de abrir, e um segundo `gio launch` mostra a
# janela em ~0,9 s. Programa que já rodava não precisa disto: um abrir basta.
#
# Geral, não uma lista: depois de abrir, se o programa aparece no X (o ícone
# da bandeja é uma janelinha com a classe dele) mas nenhuma janela de verdade
# surge, abre de novo. Quem abre com janela (Discord, Steam) nunca chega lá.

_CLASSE = re.compile(r'\("([^"]*)" "([^"]*)"\)')


def classe_da_janela(desktop: str) -> str:
    ini = configparser.RawConfigParser(strict=False, interpolation=None)
    try:
        ini.read(desktop, encoding="utf-8")
        classe = ini.get("Desktop Entry", "StartupWMClass", fallback="")
    except (configparser.Error, UnicodeDecodeError):
        classe = ""
    return (classe or Path(desktop).stem.split(".")[-1]).lower()


def _no_x(classe: str) -> bool:
    """Alguma janela do programa existe, mesmo invisível (ícone de bandeja)."""
    try:
        arvore = subprocess.run(["xwininfo", "-root", "-tree"], capture_output=True,
                                text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return any(classe in (a.lower(), b.lower()) for a, b in _CLASSE.findall(arvore))


def _tem_janela(classe: str) -> bool:
    """Uma janela de verdade, que o gerenciador de janelas mostra."""
    try:
        lista = subprocess.run(["wmctrl", "-lx"], capture_output=True,
                               text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return True  # sem como saber: não insiste
    return any(classe in linha.split()[2].lower() for linha in lista.splitlines()
               if len(linha.split()) > 2)


def _trazer_da_bandeja(comando: list[str], classe: str) -> None:
    fim = time.monotonic() + 20
    while time.monotonic() < fim:          # espera o programa subir
        if _tem_janela(classe):
            return
        if _no_x(classe):
            break
        time.sleep(0.25)
    else:
        return
    time.sleep(1.0)                        # dá a chance de a janela vir sozinha
    if not _tem_janela(classe):
        _abrir(comando)


def executar(atalho: Atalho, comandos: Comandos) -> Resultado:
    if atalho.tipo == "app":
        # Programa instalado: o `gio launch` lê o próprio .desktop do menu, do
        # mesmo jeito que clicar no ícone. O alvo é o caminho do .desktop,
        # que veio do catálogo do sistema e não do modelo.
        comando = ["gio", "launch", atalho.alvo]
        if shutil.which("gio") is None or not Path(atalho.alvo).is_file():
            return Resultado(False, f"Não consegui abrir {atalho.nome}.", comando)
        classe = classe_da_janela(atalho.alvo)
        ja_rodava = shutil.which("xwininfo") is not None and _no_x(classe)
        try:
            _abrir(comando)
        except OSError as e:
            return Resultado(False, f"Não consegui abrir {atalho.nome}: {e}", comando)
        if not ja_rodava and shutil.which("wmctrl") and shutil.which("xwininfo"):
            # Em segundo plano: a resposta falada não espera os ~3 s.
            threading.Thread(target=_trazer_da_bandeja, args=(comando, classe),
                             daemon=True).start()
        return Resultado(True, f"Abrindo {atalho.nome}.", comando)

    executavel = {
        "site": comandos.site,
        "pasta": comandos.pasta,
        "vscode": comandos.vscode,
    }[atalho.tipo]

    if shutil.which(executavel) is None:
        return Resultado(
            False,
            f"Não consigo abrir {atalho.nome}: o programa {executavel} não está "
            "instalado.",
        )

    alvo = atalho.alvo
    if atalho.tipo in ("pasta", "vscode"):
        caminho = Path(alvo).expanduser()
        # Um HD desmontado ou uma pasta movida daria um erro silencioso do
        # xdg-open. Melhor dizer em voz alta o que houve.
        if not caminho.exists():
            return Resultado(
                False,
                f"O caminho de {atalho.nome} não existe: {caminho}. "
                "O disco pode não estar montado.",
            )
        alvo = str(caminho)

    comando = [executavel, alvo]
    try:
        _abrir(comando)
    except OSError as e:
        return Resultado(False, f"Não consegui abrir {atalho.nome}: {e}", comando)

    return Resultado(True, f"Abrindo {atalho.nome}.", comando)
