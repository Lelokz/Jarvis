#!/usr/bin/env python3
"""Servidor do timbre do JARVIS dublado (RVC treinado no Applio, out/2026).

A Kokoro gera a fala (no Jarvis) e este servidor troca o timbre pelo do
JARVIS do filme. Substitui a F5 porque o "s" dela estourava e abafava, e
nenhum filtro resolvia; o Léo aprovou a receita R1 de ouvido (20/10/2026).

Roda na venv do Applio, com o PyTorch, de dentro da pasta do Applio. Não
importa nada do pacote `jarvis`: se cair, o Jarvis fala com a Kokoro.

Protocolo (socket unix, uma conexão por frase):
    -> {"taxa": 24000, "n": <bytes>}\\n + n bytes de PCM int16   ou  {"ping": true}\\n
    <- {"taxa": 40000, "n": <bytes>}\\n + n bytes de PCM int16   ou  {"erro": "..."}\\n
    <- (ping) {"ok": true, "receita": "<modelo e ajustes>"}\\n

O modelo é PESSOAL (ESCOPO §4, decisão do Léo): fica fora do git.

    cd <applio> && .venv/bin/python servidor_rvc.py --modelo M.pth --index M.index
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import socket
import sys
import time

import numpy as np


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--modelo", required=True)
    p.add_argument("--index", required=True)
    p.add_argument("--socket", default=os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
                                                    "jarvis-rvc.sock"))
    # A receita R1 que o Léo aprovou: a Kokoro fala ~1 semitom acima do
    # JARVIS (136 x 127 Hz); índice 0,5 e proteção 0,33 (padrões do Applio).
    p.add_argument("--tom", type=float, default=-1)
    p.add_argument("--indice", type=float, default=0.5)
    p.add_argument("--protecao", type=float, default=0.33)
    a = p.parse_args()

    inicio = time.monotonic()
    sys.path.insert(0, os.getcwd())
    import faiss
    import librosa
    from rvc.infer.infer import VoiceConverter

    # O Applio relê o índice (46 MB) do disco e o reconstrói inteiro a cada
    # conversão (~1 s fixo por frase); aqui os dois ficam na memória.
    class IndiceGuardado:
        def __init__(self, indice):
            self.indice, self.ntotal = indice, indice.ntotal
            self.tudo = indice.reconstruct_n(0, indice.ntotal)

        def reconstruct_n(self, *_):
            return self.tudo

        def __getattr__(self, nome):
            return getattr(self.indice, nome)

    ler_indice = faiss.read_index
    faiss.read_index = functools.lru_cache(maxsize=2)(lambda c: IndiceGuardado(ler_indice(c)))
    # E recarrega do zero o medidor de tom (rmvpe) em toda frase: ~1,5 s dos
    # ~1,8 s de cada conversão (medido, 20/10/2026). Um só, carregado uma vez.
    import rvc.infer.pipeline as pipeline_applio
    rmvpe_original = pipeline_applio.RMVPE
    pipeline_applio.RMVPE = functools.lru_cache(maxsize=1)(
        lambda device, sample_rate, hop_size: rmvpe_original(
            device=device, sample_rate=sample_rate, hop_size=hop_size))
    marcas = [f"importar {time.monotonic() - inicio:.1f}s"]
    vc = VoiceConverter()
    vc.get_vc(a.modelo, 0)
    vc.load_hubert("contentvec")
    marcas.append(f"modelos {time.monotonic() - inicio:.1f}s")

    def converter(audio: np.ndarray, taxa: int) -> np.ndarray:
        """O mesmo caminho do `core.py infer` do teste aprovado, sem arquivos."""
        if taxa != 16000:
            audio = librosa.resample(audio, orig_sr=taxa, target_sr=16000, res_type="soxr_vhq")
        pico = np.abs(audio).max() / 0.95
        if pico > 1:
            audio = audio / pico
        return vc.vc.pipeline(
            model=vc.hubert_model, net_g=vc.net_g, sid=0, audio=audio, pitch=a.tom,
            f0_method="rmvpe", file_index=a.index, index_rate=a.indice,
            pitch_guidance=vc.use_f0, volume_envelope=1.0, version=vc.version,
            protect=a.protecao, f0_autotune=False, f0_autotune_strength=1,
            proposed_pitch=False, proposed_pitch_threshold=155.0)

    # Aquece com um "falso tom de voz" (com silêncio a 1ª frase de verdade
    # ainda levava 5,6 s em vez de ~1 s).
    t = np.arange(48000) / 24000
    falso = (0.2 * np.sin(2 * np.pi * 130 * t) * (1 + np.sin(2 * np.pi * 3 * t))).astype(np.float32)
    for _ in range(2):
        converter(falso, 24000)
    marcas.append(f"aquecer {time.monotonic() - inicio:.1f}s")
    print(" · ".join(marcas), flush=True)
    if os.path.exists(a.socket):
        os.unlink(a.socket)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(a.socket)
    os.chmod(a.socket, 0o600)
    srv.listen(4)
    # A receita vai no ping: o Jarvis guarda as frases repetidas em disco, numa
    # pasta por receita (trocar o modelo ou o tom não reaproveita áudio velho).
    receita = hashlib.sha1(f"{a.modelo}|{os.path.getmtime(a.modelo)}|{a.index}|{a.tom}|"
                           f"{a.indice}|{a.protecao}".encode()).hexdigest()[:12]
    print(f"timbre pronto em {time.monotonic() - inicio:.1f}s: {a.socket}", flush=True)

    while True:
        con, _ = srv.accept()
        with con:
            try:
                arq = con.makefile("rb")
                pedido = json.loads(arq.readline() or b"{}")
                if pedido.get("ping"):
                    con.sendall(json.dumps({"ok": True, "receita": receita}).encode() + b"\n")
                    continue
                bruto = arq.read(pedido["n"])
                audio = np.frombuffer(bruto, dtype=np.int16).astype(np.float32) / 32768
                ini = time.monotonic()
                saida = converter(audio, pedido["taxa"])
                pcm = (np.clip(saida, -1, 1) * 32767).astype(np.int16).tobytes()
                con.sendall(json.dumps({"taxa": vc.tgt_sr, "n": len(pcm)}).encode() + b"\n" + pcm)
                print(f"{len(audio) / pedido['taxa']:.1f}s de fala em "
                      f"{time.monotonic() - ini:.2f}s", flush=True)
            except Exception as e:  # uma frase ruim não derruba o servidor
                try:
                    con.sendall(json.dumps({"erro": str(e)}).encode() + b"\n")
                except OSError:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
