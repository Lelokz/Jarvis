"""Pedidos de outras pessoas ao Jarvis que esperam o Sim do dono no celular
(o grupo da família, 23/10/2026): "abre a pasta X", "manda mensagem pra Y".

Como o desbloqueio do PC: o app mostra o pedido (notificação + aviso
Sim/Não), a resposta chega na porta remota (`/aprovacao`, com a chave do
app) e quem pediu a aprovação (`jarvis/grupo`) vê o resultado aqui.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path

ARQUIVO = Path.home() / ".local/share/jarvis/aprovacoes.json"
VALIDADE_S = 5 * 60
_trava = threading.Lock()


def _ler() -> list[dict]:
    try:
        lista = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        return lista if isinstance(lista, list) else []
    except (OSError, ValueError):
        return []


def _gravar(lista: list[dict]) -> None:
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.touch(mode=0o600, exist_ok=True)
    # Só as das últimas 24 h: é uma fila, não um histórico.
    ARQUIVO.write_text(json.dumps([a for a in lista if a["criado"] > time.time() - 86400]),
                       encoding="utf-8")


def criar(quem: str, pedido: str, origem: str = "grupo") -> dict:
    with _trava:
        aprovacao = {"id": secrets.token_hex(8), "quem": quem[:60], "pedido": pedido[:500],
                     "origem": origem, "criado": time.time(), "expira_em": time.time() + VALIDADE_S,
                     "estado": "esperando"}
        _gravar(_ler() + [aprovacao])
        return aprovacao


def pendentes() -> list[dict]:
    agora = time.time()
    return [a for a in _ler() if a["estado"] == "esperando" and a["expira_em"] > agora]


def responder(id_aprovacao: str, sim: bool) -> str:
    """A resposta do celular: "aprovado", "recusado" ou "expirou"."""
    with _trava:
        lista = _ler()
        for a in lista:
            if secrets.compare_digest(str(a["id"]), str(id_aprovacao)) and a["estado"] == "esperando":
                if a["expira_em"] < time.time():
                    return "expirou"
                a["estado"] = "aprovado" if sim else "recusado"
                _gravar(lista)
                return a["estado"]
        return "expirou"


def resolvidas(origem: str) -> list[dict]:
    """As que já têm resposta (ou venceram) e ainda não foram tratadas por
    quem pediu. Cada uma sai uma vez só (marca "tratada")."""
    with _trava:
        lista = _ler()
        saida = []
        agora = time.time()
        for a in lista:
            if a.get("origem") != origem or a.get("tratada"):
                continue
            if a["estado"] == "esperando" and a["expira_em"] < agora:
                a["estado"] = "expirou"
            if a["estado"] != "esperando":
                a["tratada"] = True
                saida.append(dict(a))
        if saida:
            _gravar(lista)
        return saida
