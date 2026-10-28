"""O teste do microfone da tela 6 do instalador: ouve o microfone e diz, a cada
décimo de segundo, o volume, o ruído do ambiente e se ouviu "Hey Jarvis" ou
"Hey Friday" (o openWakeWord de verdade, com os limiares do config.toml).

Uma linha JSON por evento na saída; para quando a entrada (stdin) fecha ou em
3 minutos. Roda com o Python da NOVA instalada (o do instalador não tem o
sounddevice nem o openWakeWord).

    .venv/bin/python -m jarvis.teste_microfone [--entrada <id do pactl>]
"""

from __future__ import annotations

import argparse
import json
import math
import queue
import sys
import threading
import time

import numpy as np
import sounddevice as sd

from jarvis import config, som, wakeword

TAXA = 16000
BLOCO = 1280  # 80 ms: o que o openWakeWord quer por vez


def _dizer(**dados) -> None:
    print(json.dumps(dados, ensure_ascii=False), flush=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--entrada", default=None, help="o microfone (id do pactl); vazio = o padrão")
    a = p.parse_args()
    if a.entrada is not None:
        som.guardar(entrada=a.entrada)
    som.aplicar()

    cfg = config.carregar()
    modelos = {"jarvis": cfg.dir_modelos_wake / f"{cfg.wakeword.modelo}.onnx"}
    limiares = {"jarvis": cfg.wakeword.limiar}
    if cfg.friday is not None:
        modelos["friday"] = cfg.dir_modelos_wake / f"{cfg.friday.modelo_wake}.onnx"
        limiares["friday"] = cfg.friday.limiar
    modelo = wakeword.carregar_modelo(list(modelos.values()), cfg.dir_modelos_wake)
    nomes = {caminho.stem: quem for quem, caminho in modelos.items()}

    # Para quando o instalador fecha a entrada (trocou de tela).
    fim = threading.Event()
    threading.Thread(target=lambda: (sys.stdin.read(), fim.set()), daemon=True).start()

    fila: queue.Queue[np.ndarray] = queue.Queue()
    niveis: list[float] = []
    ultimo_aviso, ultima_vez = 0.0, {quem: 0.0 for quem in modelos}
    try:
        fluxo = sd.InputStream(samplerate=TAXA, blocksize=BLOCO, channels=1, dtype="int16",
                               callback=lambda dados, *_: fila.put(dados[:, 0].copy()))
    except Exception as erro:  # sem microfone, ou ocupado
        _dizer(erro=f"Não consegui abrir o microfone: {erro}")
        return 1
    inicio = time.monotonic()
    with fluxo:
        while not fim.is_set() and time.monotonic() - inicio < 180:
            try:
                bloco = fila.get(timeout=0.5)
            except queue.Empty:
                continue
            rms = math.sqrt(float(np.mean(bloco.astype(np.float32) ** 2))) or 1.0
            nivel = 20 * math.log10(rms / 32768)
            niveis = (niveis + [nivel])[-100:]
            notas = modelo.predict(bloco)
            agora = time.monotonic()
            for nome_modelo, nota in notas.items():
                quem = nomes.get(nome_modelo)
                if quem and nota >= limiares[quem] and agora - ultima_vez[quem] > 2.0:
                    ultima_vez[quem] = agora
                    _dizer(ouviu=quem, nota=round(float(nota), 2))
            if agora - ultimo_aviso >= 0.1:
                ultimo_aviso = agora
                # O ruído é o volume do ambiente quando ninguém fala: o mais baixo dos últimos 8 s.
                _dizer(nivel=round(nivel, 1), ruido=round(sorted(niveis)[len(niveis) // 10], 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
