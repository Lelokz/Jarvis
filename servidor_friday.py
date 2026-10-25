#!/usr/bin/env python3
"""Servidor da voz da Friday (F5-TTS treinado na Emilia dublada, out/2026).

O mesmo protocolo do `servidor_voz.py` (o cliente é a mesma `VozF5`), na
mesma venv da voz. O que muda, tudo medido e escolhido de ouvido pelo Léo
em 24/10/2026:

- **12 etapas (EPSS)** em vez de 32: ~1 s por frase em vez de ~2,4 s. Ele
  escolheu às cegas ("levemente robotizada, mas fica até mais legal").
- **Pausa depois da referência**: o F5 corta o silêncio do fim dela e deixa
  50 ms; a última sílaba vazava para o começo de cada frase.
- **Corte do "sonzinho"**: uma sílaba solta curta seguida de silêncio no
  começo (vício dos recortes de treino) sai.
- **Pergunta de sim/não sobe no fim**: na dublagem ~70% das perguntas
  descem, e o modelo aprendeu isso. PSOLA (Praat) só no fim, e só o que
  falta para subir uns 4 semitons.
- **Sem estouro**: o F5 gera com pico de até 1,5; cada frase é baixada para
  pico 0,9 antes de virar int16 (antes, era cortada no teto).

Protocolo (socket unix, uma conexão por fala):
    -> {"texto": "..."}\\n          ou  {"ping": true}\\n
    <- {"taxa": 24000, "n": <bytes>}\\n + n bytes de PCM int16, uma por frase
    <- {"fim": true}\\n                 ou  {"erro": "..."}\\n

A voz e o modelo são PESSOAIS (ESCOPO §4): ficam fora do git, em
~/.local/share/jarvis/voz-friday.

    servidor_friday.py [--pasta ~/.local/share/jarvis/voz-friday] [--ref limpa1] [--nfe 12]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np
import parselmouth
import torchaudio
from f5_tts.api import F5TTS
from f5_tts.infer import utils_infer
from num2words import num2words
from parselmouth.praat import call
from pydub import AudioSegment

_tirar_bordas = utils_infer.remove_silence_edges
utils_infer.remove_silence_edges = lambda seg, *a, **k: _tirar_bordas(seg, *a, **k) + AudioSegment.silent(duration=400)

# Pergunta aberta ("Por que...?", "Onde...?") desce também em português: fica como está.
ABERTA = re.compile(r"^\W*(o que|que|qual|quais|quem|quando|onde|como|por ?que|pra que|quanto|cad[eê])\b", re.I)


def normalizar(texto: str) -> str:
    """O modelo PT-BR quer minúsculas e número por extenso."""
    t = re.sub(r"[*_`#>]+", "", texto)
    t = re.sub(r"(\d+)h(\d+)", lambda m: f"{m[1]} e {m[2]}", t)
    t = re.sub(r"(\d+)%", r"\1 por cento", t)
    t = re.sub(r"\d+", lambda m: num2words(int(m[0]), lang="pt_BR"), t)
    return " ".join(t.lower().split())


def frases(texto: str) -> list[str]:
    """Frase por frase (cada uma é gerada enquanto a anterior toca); frase
    muito longa quebra nas vírgulas."""
    pedacos = []
    for f in re.split(r"(?<=[.!?…])\s+", texto.strip()):
        if not f.strip():
            continue
        if len(f) <= 100:
            pedacos.append(f)
            continue
        atual = ""
        for parte in re.split(r"(?<=,)\s+", f):
            atual = f"{atual} {parte}".strip()
            if len(atual) >= 40:
                pedacos.append(atual)
                atual = ""
        if atual:
            if pedacos:
                pedacos[-1] = f"{pedacos[-1]} {atual}"
            else:
                pedacos.append(atual)
    return pedacos


def tirar_pedacinho(audio: np.ndarray, sr: int) -> np.ndarray:
    """Nos primeiros 0,5 s: voz curta (<= 0,25 s), silêncio (>= 0,07 s) e voz
    de novo = sílaba solta; corta até o silêncio."""
    q = int(0.01 * sr)
    env = np.array([np.sqrt(np.mean(audio[i:i + q] ** 2)) for i in range(0, min(len(audio), sr) - q, q)])
    if not len(env):
        return audio
    voz = env > np.percentile(env, 95) * 0.12
    i = int(np.argmax(voz))
    if not voz[i] or i > 40:
        return audio
    j = i
    while j < len(voz) and voz[j]:
        j += 1
    k = j
    while k < len(voz) and not voz[k]:
        k += 1
    if (j - i) <= 25 and (k - j) >= 7 and k < 50 and k < len(voz):
        return audio[max(0, (k - 5) * q):]
    return audio


def subir_pergunta(audio: np.ndarray, sr: int, alvo: float = 4.0, janela: float = 0.45) -> np.ndarray:
    """Sobe o tom do fim só o que falta para chegar a `alvo` semitons."""
    som = parselmouth.Sound(audio.astype(np.float64), sampling_frequency=sr)
    man = call(som, "To Manipulation", 0.01, 120, 700)
    tier = call(man, "Extract pitch tier")
    pitch = som.to_pitch(time_step=0.01, pitch_floor=120, pitch_ceiling=700)
    f0 = pitch.selected_array["frequency"]
    tempos = pitch.xs()
    voz = f0 > 0
    k = len(voz) - 1  # o último trecho de voz de verdade (>= 5 quadros), não um quadro de ruído
    while k >= 0 and not (voz[k] and voz[max(0, k - 4):k + 1].all()):
        k -= 1
    validos = np.where(voz[:k + 1])[0]
    if k < 0 or len(validos) < 10:
        return audio
    agora = 12 * np.log2(np.median(f0[validos[-6:]]) / np.median(f0[validos[len(validos) // 3: 2 * len(validos) // 3]]))
    semitons = float(np.clip(alvo - agora, 0, 9))
    if semitons < 0.5:
        return audio
    fim = tempos[k]
    ini = fim - janela
    for n in range(call(tier, "Get number of points"), 0, -1):
        t = call(tier, "Get time from index", n)
        if t > ini:
            f = call(tier, "Get value at index", n)
            call(tier, "Remove point", n)
            call(tier, "Add point", t, f * 2 ** (semitons / 12 * min(1.0, (t - ini) / janela) ** 1.5))
    call([tier, man], "Replace pitch tier")
    novo = call(man, "Get resynthesis (overlap-add)")
    return np.asarray(novo.values[0], dtype=np.float32)[: len(audio)]


# O que a Friday fala sempre igual: pronto desde a subida.
FIXAS = ["oi, chefinho!", "tá bom!", "parei.", "pausei.", "voltando!", "próxima!", "anterior.", "prontinho!"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pasta", default=str(Path.home() / ".local/share/jarvis/voz-friday"))
    p.add_argument("--ref", default="limpa1")
    p.add_argument("--socket", default=os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "jarvis-friday.sock"))
    p.add_argument("--nfe", type=int, default=12)
    # Sem o acabamento (corte, pergunta, volume): só para comparar de ouvido.
    p.add_argument("--cru", action="store_true")
    a = p.parse_args()

    inicio = time.monotonic()
    pasta = Path(a.pasta)
    tts = F5TTS(model="F5TTS_Base", ckpt_file=str(pasta / "modelo/friday-emilia.safetensors"),
                vocab_file=str(pasta / "modelo/vocab.txt"), device="cuda")
    # A referência é preparada uma vez só (antes, a cada frase).
    arq, ref_texto = utils_infer.preprocess_ref_audio_text(
        str(pasta / f"ref/{a.ref}.wav"), normalizar((pasta / f"ref/{a.ref}.txt").read_text()), show_info=lambda *_: None)
    ref = torchaudio.load(arq)

    guardadas: OrderedDict[str, bytes] = OrderedDict()
    receita = hashlib.sha1(f"friday|{a.ref}|{a.nfe}|{'cru' if a.cru else 'v1'}".encode()).hexdigest()[:12]
    disco = pasta / "cache" / receita
    disco.mkdir(parents=True, exist_ok=True)

    def gerar(frase: str) -> tuple[bytes, int]:
        chave = normalizar(frase)
        arquivo = disco / (hashlib.sha1(chave.encode()).hexdigest() + ".pcm")
        if chave in guardadas:
            guardadas.move_to_end(chave)
            return guardadas[chave], 24000
        if arquivo.exists():
            guardadas[chave] = arquivo.read_bytes()
            return guardadas[chave], 24000
        wav, taxa, _ = next(utils_infer.infer_batch_process(ref, ref_texto, [chave], tts.ema_model, tts.vocoder,
                                                            nfe_step=a.nfe, device="cuda"))
        audio = np.asarray(wav, dtype=np.float32)
        if a.cru:
            pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes()
        else:
            audio = tirar_pedacinho(audio, taxa)
            if frase.strip().endswith("?") and not ABERTA.search(frase):
                audio = subir_pergunta(audio, taxa)
            audio = audio * (0.9 / max(1e-4, float(np.abs(audio).max())))
            pcm = (audio * 32767).astype(np.int16).tobytes()
        if len(chave) <= 60:
            guardadas[chave] = pcm
            if len(guardadas) > 300:
                guardadas.popitem(last=False)
            arquivo.write_bytes(pcm)
        return pcm, taxa

    for fixa in FIXAS:  # aquece a placa e deixa as respostas fixas prontas
        gerar(fixa)
    if os.path.exists(a.socket):
        os.unlink(a.socket)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(a.socket)
    os.chmod(a.socket, 0o600)
    srv.listen(4)
    print(f"voz da Friday pronta em {time.monotonic() - inicio:.1f}s: {a.socket}", flush=True)

    while True:
        con, _ = srv.accept()
        with con:
            try:
                pedido = json.loads(con.makefile("rb").readline() or b"{}")
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
