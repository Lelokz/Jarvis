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

No Windows (sem PulseAudio): a lista vem do PortAudio (DirectSound, que tem o
nome inteiro do aparelho e aceita qualquer taxa), a escolha é o nome, e quem
abre um fluxo pergunta aparelho() na hora: o mesmo "vale no próximo fluxo".
Aparelho plugado com a NOVA ligada só aparece depois de religar.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ESCOLHA = Path.home() / ".local/share/jarvis/som.json"
WINDOWS = os.name == "nt"
# O dispositivo que o microfone e a fala recebem quando vale a escolha dos Ajustes.
# No Linux é o "pulse" do PortAudio (que obedece PULSE_SINK/PULSE_SOURCE); no Windows,
# uma marca que aparelho() troca pelo número do aparelho escolhido.
DISPOSITIVO = "nova:escolha" if WINDOWS else "pulse"


def _directsound() -> tuple[list[dict], dict]:
    """Os aparelhos do DirectSound (com o índice do PortAudio) e o host dele."""
    import sounddevice as sd
    host = next(h for h in sd.query_hostapis() if "DirectSound" in h["name"])
    aparelhos = [dict(d, indice=i) for i, d in enumerate(sd.query_devices()) if i in host["devices"]]
    return aparelhos, host


def _padrao_windows(entrada: bool) -> str:
    """O nome do aparelho padrão do Windows (o "Driver de som primário" do DirectSound
    não diz qual é; o WASAPI diz)."""
    import sounddevice as sd
    try:
        wasapi = next(h for h in sd.query_hostapis() if "WASAPI" in h["name"])
        i = wasapi["default_input_device" if entrada else "default_output_device"]
        return sd.query_devices(i)["name"] if i >= 0 else ""
    except (StopIteration, Exception):
        return ""


def aparelho(dispositivo, entrada: bool):
    """O que vai para o `device=` do PortAudio na hora de abrir o fluxo. Só muda a
    marca do Windows: vira o índice do aparelho escolhido (ou None = o padrão)."""
    if dispositivo != DISPOSITIVO or not WINDOWS:
        return dispositivo
    nome = escolha()["entrada" if entrada else "saida"]
    if not nome:
        return None
    try:
        aparelhos, _ = _directsound()
    except Exception:
        return None
    canais = "max_input_channels" if entrada else "max_output_channels"
    return next((a["indice"] for a in aparelhos if a["name"] == nome and a[canais] > 0), None)


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
    if WINDOWS:
        try:
            _directsound()
            return True
        except Exception:
            return False
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


def _listar_windows() -> dict[str, Any]:
    aparelhos, host = _directsound()
    # Os "primários" do DirectSound são só apelidos do padrão: ficam de fora.
    reais = [a for a in aparelhos if a["indice"] not in (host["default_input_device"], host["default_output_device"])]
    saidas = sorted({a["name"] for a in reais if a["max_output_channels"] > 0})
    entradas = sorted({a["name"] for a in reais if a["max_input_channels"] > 0})
    atual = escolha()
    return {
        "saidas": [{"id": n, "nome": n} for n in saidas],
        "entradas": [{"id": n, "nome": n} for n in entradas],
        "padrao_saida": _padrao_windows(entrada=False),
        "padrao_entrada": _padrao_windows(entrada=True),
        "saida": atual["saida"] if atual["saida"] in saidas else "",
        "entrada": atual["entrada"] if atual["entrada"] in entradas else "",
    }


def listar() -> dict[str, Any]:
    """Para a janela: os aparelhos, o padrão do sistema e a escolha."""
    if WINDOWS:
        return _listar_windows()
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
    aparelho escolhido que sumiu (fone desplugado) cai no padrão. No Windows não há
    nada a pôr no ambiente: aparelho() lê a escolha quando o fluxo abre."""
    if WINDOWS:
        return
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

