"""O pedido de desbloquear o PC, esperando o Sim do Léo no celular.

O Jarvis (pela ferramenta `pedir_desbloqueio`, só com a voz do Léo) cria o
pedido; o app do celular mostra "Desbloquear o PC?"; a resposta chega na
porta remota (`/desbloqueio`, com a chave do app) e só então a tela destrava.
Um pedido vale por poucos minutos e por uma resposta só.
"""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path

from . import tela

ARQUIVO = Path.home() / ".local/share/jarvis/desbloqueio.json"
VALIDADE_S = 3 * 60


def criar() -> dict:
    pedido = {"id": secrets.token_hex(8), "pedido_em": time.time(),
              "expira_em": time.time() + VALIDADE_S}
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.touch(mode=0o600, exist_ok=True)
    ARQUIVO.write_text(json.dumps(pedido), encoding="utf-8")
    return pedido


def pendente() -> dict | None:
    try:
        pedido = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(pedido, dict) or pedido.get("expira_em", 0) < time.time():
        return None
    return pedido


def responder(id_pedido: str, sim: bool) -> str:
    """A resposta do celular. Devolve o que aconteceu, para o app mostrar."""
    pedido = pendente()
    if pedido is None or not secrets.compare_digest(str(pedido.get("id")), str(id_pedido)):
        return "expirou"
    ARQUIVO.unlink(missing_ok=True)  # uma resposta só
    if not sim:
        return "recusado"
    return "desbloqueado" if tela.desbloquear() else "falhou"
