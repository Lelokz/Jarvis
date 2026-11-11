"""Os ajustes da janela (beta 0.6.5) que não são som: o volume da voz do
Jarvis no PC, o nome de quem usa e os grupos do WhatsApp. Ficam em
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
                          # Os grupos do WhatsApp onde o Jarvis responde (jarvis/grupo); quantos
                          # o Léo quiser (09/11/2026; antes era um só, o "grupo_jid").
                          "grupos": [], "grupo_ligado": False,
                          # Onde o instalador pôs as vozes dubladas (jarvis/vozes.py).
                          "pasta_vozes": "",
                          # Os programas das vozes dubladas, quando foi o instalador que pôs.
                          "programas_vozes": "",
                          # Quem atende quando a NOVA liga (o instalador pergunta).
                          "persona_inicial": "jarvis",
                          # O modo code (10/11/2026): narração, microfone aberto e quem programa.
                          "code_narracao": "normal", "code_janela_s": 120, "code_persona": "atual",
                          # A cara da janela e do app (11/11/2026): "escuro" ou "claro".
                          "tema": "escuro"}


def limpar_nome(nome: str) -> str:
    """O nome de quem usa (beta 0.7.5): curto, uma linha, sem caractere estranho."""
    return " ".join("".join(c for c in nome if c.isalnum() or c in " -'.").split())[:30]


def nome_de_quem_usa() -> str:
    """Para as frases e para a persona; sem nome, "o usuário"."""
    return ler()["nome"]


def grupos_ativos() -> list[str]:
    """Os grupos onde o Jarvis responde agora (nenhum com a chave desligada)."""
    a = ler()
    return a["grupos"] if a["grupo_ligado"] else []


def ler() -> dict[str, Any]:
    try:
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {}
    saida = dict(PADRAO, grupos=[])
    if isinstance(dados, dict):
        volume = dados.get("volume_voz")
        if isinstance(volume, (int, float)) and not isinstance(volume, bool):
            saida["volume_voz"] = int(min(100, max(0, volume)))
        grupos = dados.get("grupos")
        if not isinstance(grupos, list):  # o arquivo antigo, de um grupo só
            grupos = [dados["grupo_jid"]] if isinstance(dados.get("grupo_jid"), str) else []
        saida["grupos"] = list(dict.fromkeys(g for g in grupos if isinstance(g, str) and g.endswith("@g.us")))
        if isinstance(dados.get("grupo_ligado"), bool):
            saida["grupo_ligado"] = dados["grupo_ligado"]
        if isinstance(dados.get("programas_vozes"), str):
            saida["programas_vozes"] = dados["programas_vozes"][:1000]
        if isinstance(dados.get("pasta_vozes"), str):
            saida["pasta_vozes"] = dados["pasta_vozes"][:1000]
        if dados.get("persona_inicial") in ("jarvis", "friday"):
            saida["persona_inicial"] = dados["persona_inicial"]
        if isinstance(dados.get("nome"), str):
            saida["nome"] = limpar_nome(dados["nome"])
        if dados.get("code_narracao") in ("pouca", "normal", "muita"):
            saida["code_narracao"] = dados["code_narracao"]
        if dados.get("code_janela_s") in (60, 120, 180, 300):
            saida["code_janela_s"] = dados["code_janela_s"]
        if dados.get("code_persona") in ("atual", "jarvis", "friday"):
            saida["code_persona"] = dados["code_persona"]
        if dados.get("tema") in ("escuro", "claro"):
            saida["tema"] = dados["tema"]
    return saida


def mudar(**novos: Any) -> dict[str, Any]:
    atual = ler()
    atual.update({k: v for k, v in novos.items() if k in PADRAO})
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps(atual), encoding="utf-8")
    return ler()
