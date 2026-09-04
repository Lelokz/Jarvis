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

import shutil
import subprocess
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


def executar(atalho: Atalho, comandos: Comandos) -> Resultado:
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
