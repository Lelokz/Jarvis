#!/usr/bin/env python3
"""Servidor da voz do JARVIS dublado (F5-TTS treinado, out/2026).

Roda na venv da voz (`~/.local/share/jarvis/voz-jarvis/venv`, que tem o
PyTorch), não na do Jarvis: o assistente fica leve e, se este servidor cair,
fala com a Kokoro. Não importa nada do pacote `jarvis`.

Protocolo (socket unix, uma conexão por fala):
    -> {"texto": "..."}\\n          ou  {"ping": true}\\n
    <- {"taxa": 24000, "n": <bytes>}\\n + n bytes de PCM int16, uma por frase
    <- {"fim": true}\\n                 ou  {"erro": "..."}\\n

A voz e o modelo são PESSOAIS (ESCOPO §4, decisão do Léo): ficam fora do git.

    servidor_voz.py --modelo M.safetensors --ref ref.wav --ref-texto "..." [--nfe 32]
                    [--filtro "bass=g=4:f=150:w=0.8"]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import time
from collections import OrderedDict

import numpy as np
from f5_tts.api import F5TTS
from num2words import num2words


def normalizar(texto: str) -> str:
    """O modelo PT-BR quer minúsculas e número por extenso."""
    t = re.sub(r"[*_`#>]+", "", texto)
    t = re.sub(r"(\d+)h(\d+)", lambda m: f"{m[1]} e {m[2]}", t)
    t = re.sub(r"(\d+)%", r"\1 por cento", t)
    t = re.sub(r"\d+", lambda m: num2words(int(m[0]), lang="pt_BR"), t)
    return " ".join(t.lower().split())


def frases(texto: str) -> list[str]:
    return [f for f in re.split(r"(?<=[.!?…])\s+", texto.strip()) if f.strip()]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--modelo", required=True)
    p.add_argument("--ref", required=True)
    p.add_argument("--ref-texto", required=True)
    p.add_argument("--socket", default=os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
                                                    "jarvis-voz.sock"))
    # 32 passos: com 16 sai em metade do tempo, mas a voz borbulha mais e
    # fica fina (o Léo escolheu de ouvido a versão de 32, 19/10/2026).
    p.add_argument("--nfe", type=int, default=32)
    # Filtro do ffmpeg aplicado em cada frase (ex.: graves realçados). Vazio = nenhum.
    p.add_argument("--filtro", default="")
    p.add_argument("--velocidade", type=float, default=1.0)
    a = p.parse_args()

    inicio = time.monotonic()
    from importlib.resources import files
    vocab = files("f5_tts").joinpath("infer/examples/vocab.txt")
    tts = F5TTS(model="F5TTS_Base", ckpt_file=a.modelo, vocab_file=str(vocab), device="cuda")
    ref_texto = normalizar(a.ref_texto)
    ffmpeg = shutil.which("ffmpeg")

    def filtrar(audio: np.ndarray, taxa: int) -> np.ndarray:
        """O mesmo filtro do ffmpeg do teste aprovado. Sem ffmpeg, sai sem filtro."""
        if not a.filtro or ffmpeg is None:
            return audio
        r = subprocess.run([ffmpeg, "-loglevel", "error", "-f", "f32le", "-ar", str(taxa), "-ac", "1",
                            "-i", "-", "-af", a.filtro, "-f", "f32le", "-"],
                           input=audio.astype(np.float32).tobytes(), capture_output=True)
        return np.frombuffer(r.stdout, dtype=np.float32) if r.returncode == 0 and r.stdout else audio

    # O que se repete ("Pois não?", "Tá bom.", "Parei.") sai na hora da 2ª vez.
    guardadas: OrderedDict[str, bytes] = OrderedDict()

    def gerar(frase: str) -> tuple[bytes, int]:
        chave = normalizar(frase)
        if chave in guardadas:
            guardadas.move_to_end(chave)
            return guardadas[chave], 24000
        wav, taxa, _ = tts.infer(ref_file=a.ref, ref_text=ref_texto, gen_text=chave,
                                 nfe_step=a.nfe, speed=a.velocidade, show_info=lambda *_: None)
        audio = filtrar(np.asarray(wav, dtype=np.float32), taxa)
        pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes()
        if len(chave) <= 40:
            guardadas[chave] = pcm
            if len(guardadas) > 200:
                guardadas.popitem(last=False)
        return pcm, taxa

    gerar("pois não?")  # aquece e já deixa a saudação pronta
    if os.path.exists(a.socket):
        os.unlink(a.socket)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(a.socket)
    os.chmod(a.socket, 0o600)
    srv.listen(4)
    print(f"voz pronta em {time.monotonic() - inicio:.1f}s: {a.socket}", flush=True)

    while True:
        con, _ = srv.accept()
        with con:
            try:
                arq = con.makefile("rb")
                pedido = json.loads(arq.readline() or b"{}")
                if pedido.get("ping"):
                    con.sendall(b'{"ok": true}\n')
                    continue
                for frase in frases(str(pedido.get("texto") or "")):
                    pcm, taxa = gerar(frase)
                    con.sendall(json.dumps({"taxa": taxa, "n": len(pcm)}).encode() + b"\n" + pcm)
                con.sendall(b'{"fim": true}\n')
            except (OSError, ValueError) as e:
                try:
                    con.sendall(json.dumps({"erro": str(e)}).encode() + b"\n")
                except OSError:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
