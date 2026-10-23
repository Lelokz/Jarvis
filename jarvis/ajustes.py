"""Os ajustes da janela (beta 0.6.5) que não são som: o volume da voz do
Jarvis no PC e as notificações da escola NO PC (o app do celular tem o
interruptor dele). Ficam em
~/.local/share/jarvis/ajustes.json; quem usa lê na hora (a escola roda em
outro processo).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ARQUIVO = Path.home() / ".local/share/jarvis/ajustes.json"
# 100 = o volume de sempre, que é o TETO: o volume já machucou o ouvido do
# Léo uma vez (HISTORIA). Daqui só se abaixa.
PADRAO: dict[str, Any] = {"volume_voz": 100, "notificar_escola": True}


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
        if isinstance(dados.get("notificar_escola"), bool):
            saida["notificar_escola"] = dados["notificar_escola"]
    return saida


def mudar(**novos: Any) -> dict[str, Any]:
    atual = ler()
    atual.update({k: v for k, v in novos.items() if k in PADRAO})
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps(atual), encoding="utf-8")
    return ler()
