"""As saídas e entradas de som do PC, pelo servidor de som do Linux
(PipeWire ou PulseAudio, os dois falam o protocolo do PulseAudio).

A lista vem do sistema, nada é chumbado: no PC de outra pessoa aparecem os
aparelhos dela. A escolha (ou "" = o padrão do sistema, que acompanha o que
estiver marcado nas configurações de som) fica em
~/.local/share/jarvis/som.json.

Como o Jarvis toca e grava por um aparelho escolhido: abre o fluxo no
dispositivo "pulse" do PortAudio, que obedece PULSE_SINK e PULSE_SOURCE no
momento em que o fluxo abre. A saída abre um fluxo por fala, então vale na
próxima frase; o microfone precisa ser reaberto (Microfone.trocar).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ESCOLHA = Path.home() / ".local/share/jarvis/som.json"
DISPOSITIVO = "pulse"


def _nome(aparelho) -> str:
    """O nome que a pessoa reconhece: "LG ULTRAGEAR (HDMI)", "fifine
    Microphone", "Saída de linha"."""
    props = aparelho.proplist
    nick = props.get("node.nick") or props.get("device.nick") or ""
    porta = aparelho.port_active.description if aparelho.port_active else ""
    if "hdmi" in aparelho.name.lower() or "displayport" in porta.lower():
        return f"{nick or 'Monitor'} (HDMI)"
    if props.get("device.bus") == "usb" or ".usb-" in aparelho.name:
        return props.get("device.product.name") or nick or aparelho.description
    # Placa de som da placa-mãe: a porta diz o que é (saída de linha, fone, microfone frontal).
    return porta or aparelho.description


def _ligado(aparelho) -> bool:
    """Sem nada plugado em nenhuma porta (microfone frontal vazio, por
    exemplo), não aparece na lista."""
    portas = aparelho.port_list
    return not portas or any(p.available != "no" for p in portas)


def disponivel() -> bool:
    try:
        import pulsectl  # noqa: F401
        with _pulse():
            return True
    except Exception:
        return False


def _pulse():
    import pulsectl
    return pulsectl.Pulse("jarvis-som")


def escolha() -> dict[str, str]:
    try:
        dados = json.loads(ESCOLHA.read_text(encoding="utf-8"))
        return {"saida": str(dados.get("saida", "")), "entrada": str(dados.get("entrada", ""))}
    except (OSError, ValueError, AttributeError):
        return {"saida": "", "entrada": ""}


def listar() -> dict[str, Any]:
    """Para a janela: os aparelhos, o padrão do sistema e a escolha."""
    with _pulse() as p:
        info = p.server_info()
        saidas = [s for s in p.sink_list() if _ligado(s)]
        entradas = [s for s in p.source_list() if not s.monitor_of_sink_name and _ligado(s)]
        padrao_saida = next((_nome(s) for s in p.sink_list() if s.name == info.default_sink_name), "")
        padrao_entrada = next((_nome(s) for s in p.source_list() if s.name == info.default_source_name), "")
    atual = escolha()
    ids_saida, ids_entrada = {s.name for s in saidas}, {s.name for s in entradas}
    return {
        "saidas": [{"id": s.name, "nome": _nome(s)} for s in saidas],
        "entradas": [{"id": s.name, "nome": _nome(s)} for s in entradas],
        "padrao_saida": padrao_saida,
        "padrao_entrada": padrao_entrada,
        # Escolhido e desplugado: vale o padrão até ele voltar.
        "saida": atual["saida"] if atual["saida"] in ids_saida else "",
        "entrada": atual["entrada"] if atual["entrada"] in ids_entrada else "",
    }


def guardar(saida: str | None = None, entrada: str | None = None) -> None:
    atual = escolha()
    if saida is not None:
        atual["saida"] = saida
    if entrada is not None:
        atual["entrada"] = entrada
    ESCOLHA.parent.mkdir(parents=True, exist_ok=True)
    ESCOLHA.write_text(json.dumps(atual), encoding="utf-8")


def aplicar() -> None:
    """Põe a escolha no ambiente: vale para o próximo fluxo que abrir. Um
    aparelho escolhido que sumiu (fone desplugado) cai no padrão."""
    atual = escolha()
    try:
        with _pulse() as p:
            existentes = {s.name for s in p.sink_list()} | {s.name for s in p.source_list()}
    except Exception:
        existentes = set()
    for chave, variavel in (("saida", "PULSE_SINK"), ("entrada", "PULSE_SOURCE")):
        if atual[chave] and atual[chave] in existentes:
            os.environ[variavel] = atual[chave]
        else:
            os.environ.pop(variavel, None)


# O volume dos outros sons enquanto o Jarvis fala (0,3 = 30% do que estava).
FATOR_ABAIXADO = 0.3


def abaixar_os_outros():
    """Abaixa tudo o que está tocando no PC (vídeo, música, jogo), menos o
    próprio Jarvis, enquanto ele fala. Devolve a função que volta cada um ao
    volume de antes. Sem servidor de som, não faz nada."""
    try:
        import pulsectl
        meu = str(os.getpid())
        antes = []
        with _pulse() as p:
            for fluxo in p.sink_input_list():
                if fluxo.proplist.get("application.process.id") == meu:
                    continue
                volume = fluxo.volume
                antes.append((fluxo.index, pulsectl.PulseVolumeInfo(list(volume.values))))
                p.volume_set(fluxo, pulsectl.PulseVolumeInfo([v * FATOR_ABAIXADO for v in volume.values]))
    except Exception:
        return lambda: None

    def voltar() -> None:
        try:
            with _pulse() as p:
                existentes = {f.index: f for f in p.sink_input_list()}
                for indice, volume in antes:
                    if indice in existentes:  # o vídeo pode ter fechado no meio
                        p.volume_set(existentes[indice], volume)
        except Exception:
            pass

    return voltar
