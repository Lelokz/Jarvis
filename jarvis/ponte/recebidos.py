"""Os anexos (fotos, vídeos, arquivos) que o Léo manda ao Jarvis, do celular
ou da janela do PC. Ficam em `protocolo.pasta_recebidos()`, a única pasta de
onde a ponte aceita anexo, e somem depois de DIAS dias."""
from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

from . import protocolo

DIAS = 14


def nome_seguro(nome: str) -> str:
    """Só o nome do arquivo, sem pasta nem caractere estranho."""
    base = Path(nome or "anexo").name
    base = re.sub(r"[^\w.\- ]", "_", base, flags=re.UNICODE).strip(" .") or "anexo"
    return base[-80:]


def _novo_caminho(nome: str) -> Path:
    pasta = protocolo.pasta_recebidos()
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    caminho = pasta / f"{time.strftime('%Y%m%d-%H%M%S')}-{nome_seguro(nome)}"
    n = 1
    while caminho.exists():
        caminho = caminho.with_name(f"{caminho.stem}-{n}{caminho.suffix}")
        n += 1
    return caminho


def guardar(nome: str, dados: bytes) -> Path:
    """O que chegou pela rede (o clipe do app)."""
    caminho = _novo_caminho(nome)
    fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(dados)
    return caminho


def copiar(origem: Path) -> Path:
    """Um arquivo do próprio PC (o clipe da janela): copiado, e não ligado,
    para o Jarvis não depender de ele continuar onde estava."""
    caminho = _novo_caminho(origem.name)
    shutil.copyfile(origem, caminho)
    os.chmod(caminho, 0o600)
    return caminho


def limpar(dias: int = DIAS) -> int:
    pasta = protocolo.pasta_recebidos()
    if not pasta.is_dir():
        return 0
    limite = time.time() - dias * 86400
    apagados = 0
    for f in pasta.iterdir():
        if f.is_file() and f.stat().st_mtime < limite:
            f.unlink(missing_ok=True)
            apagados += 1
    return apagados
