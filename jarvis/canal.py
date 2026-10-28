"""O canal entre as partes da NOVA: janela e celular ↔ assistente (jarvis.sock),
assistente ↔ servidores de voz (jarvis-rvc.sock, jarvis-friday.sock, jarvis-voz.sock).

No Linux é um socket Unix: um arquivo no $XDG_RUNTIME_DIR que só o próprio usuário
abre. O Python do Windows não tem socket Unix: lá é TCP em 127.0.0.1, numa porta
livre que o servidor escolhe e anota no mesmo arquivo. Assim o "caminho" continua
sendo o nome do canal nos dois sistemas, e quem usa não precisa saber qual é.

Só biblioteca padrão: os servidores de voz rodam em outro Python e importam daqui.
"""

from __future__ import annotations

import asyncio
import os
import socket
import stat
from pathlib import Path

WINDOWS = os.name == "nt"


def pasta() -> Path:
    """Onde os canais moram: o $XDG_RUNTIME_DIR no Linux (só o usuário entra, some no
    logout); no Windows, uma pasta da NOVA dentro do AppData do usuário."""
    if WINDOWS:
        p = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "jarvis" / "canais"
        p.mkdir(parents=True, exist_ok=True)
        return p
    return Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")


def _porta(caminho: str | Path) -> int:
    try:
        return int(Path(caminho).read_text().strip())
    except ValueError:
        # Arquivo pela metade (o servidor está subindo) ou estragado: ninguém atende.
        raise ConnectionRefusedError(f"{caminho} sem porta") from None


def conectar(caminho: str | Path, timeout: float | None = None) -> socket.socket:
    """Conecta no canal. Sem ninguém escutando: ConnectionRefusedError ou FileNotFoundError."""
    if WINDOWS:
        return socket.create_connection(("127.0.0.1", _porta(caminho)), timeout=timeout)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(caminho))
    except BaseException:
        s.close()
        raise
    return s


async def abrir(caminho: str | Path, **kw) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """O conectar() do asyncio (a porta do celular)."""
    if WINDOWS:
        return await asyncio.open_connection("127.0.0.1", _porta(caminho), **kw)
    return await asyncio.open_unix_connection(str(caminho), **kw)


def escutar(caminho: str | Path, fila: int = 8) -> socket.socket:
    """Abre o canal do lado de quem atende. O caminho tem que estar livre (ver eh_canal)."""
    if WINDOWS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.listen(fila)
        # A porta vai para um arquivo novo e depois troca de nome: quem lê nunca pega
        # o arquivo pela metade.
        meio = Path(str(caminho) + ".novo")
        meio.write_text(str(s.getsockname()[1]))
        os.replace(meio, caminho)
        return s
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    # O socket nasce já fechado para os outros usuários: sem janela entre o bind e o
    # chmod em que alguém de fora poderia conectar.
    mascara = os.umask(0o177)
    try:
        s.bind(str(caminho))
    finally:
        os.umask(mascara)
    os.chmod(caminho, 0o600)
    s.listen(fila)
    return s


def eh_canal(caminho: str | Path) -> bool:
    """O arquivo que existe nesse caminho é um canal (e pode ser apagado se ninguém atende)?"""
    if WINDOWS:
        return Path(caminho).is_file()
    return stat.S_ISSOCK(os.lstat(caminho).st_mode)
