"""Os ajustes da janela (beta 0.6.5) que não são som: o volume da voz do
Jarvis no PC, o nome de quem usa e o grupo da família. Ficam em
~/.local/share/jarvis/ajustes.json; quem usa lê na hora (o grupo roda em
outra thread).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ARQUIVO = Path.home() / ".local/share/jarvis/ajustes.json"
# 100 = o volume de sempre, que é o TETO: o volume já machucou o ouvido do
# Léo uma vez (HISTORIA). Daqui só se abaixa.
PADRAO: dict[str, Any] = {"volume_voz": 100, "nome": "",
                          # O Jarvis no grupo da família do WhatsApp (jarvis/grupo).
                          "grupo_jid": "", "grupo_ligado": False,
                          # Onde o instalador pôs as vozes dubladas (jarvis/vozes.py).
                          "pasta_vozes": ""}


def limpar_nome(nome: str) -> str:
    """O nome de quem usa (beta 0.7.5): curto, uma linha, sem caractere estranho."""
    return " ".join("".join(c for c in nome if c.isalnum() or c in " -'.").split())[:30]


def nome_de_quem_usa() -> str:
    """Para as frases e para a persona; sem nome, "o usuário"."""
    return ler()["nome"]


def ler() -> dict[str, Any]:
    try:
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {}
    saida = dict(PADRAO)
    if isinstance(dados, dict):
        volume = dados.get("volume_voz")
        if isinstance(volume, (int, float)) and not isinstance(volume, bool):
            saida["volume_voz"] = int(min(100, max(0, volume)))
        if isinstance(dados.get("grupo_jid"), str) and (not dados["grupo_jid"] or dados["grupo_jid"].endswith("@g.us")):
            saida["grupo_jid"] = dados["grupo_jid"]
        if isinstance(dados.get("grupo_ligado"), bool):
            saida["grupo_ligado"] = dados["grupo_ligado"]
        if isinstance(dados.get("pasta_vozes"), str):
            saida["pasta_vozes"] = dados["pasta_vozes"][:1000]
        if isinstance(dados.get("nome"), str):
            saida["nome"] = limpar_nome(dados["nome"])
    return saida


def mudar(**novos: Any) -> dict[str, Any]:
    atual = ler()
    atual.update({k: v for k, v in novos.items() if k in PADRAO})
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps(atual), encoding="utf-8")
    return ler()
