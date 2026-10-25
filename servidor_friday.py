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
- **Gera e confere** (25/10/2026): o F5 tem sorte a cada geração; ~37% saíam
  com palavra inventada no começo ("E prontinho...", vício dos recortes) ou
  com palavra faltando, em qualquer configuração. O Whisper ouve cada frase
  e, se não bater com o texto, gera de novo (até 3 vezes; fica a melhor).
- **Dicionário de pronúncia**: o modelo lê letra por letra e erra a sílaba
  forte ("láfora" em vez de "lá fóra"). `pronuncia.txt` na pasta da voz,
  uma troca por linha: `lá fora = lá fóra`.

Protocolo (socket unix, uma conexão por fala):
    -> {"texto": "..."}\\n          ou  {"ping": true}\\n
    <- {"taxa": 24000, "n": <bytes>}\\n + n bytes de PCM int16, uma por frase
    <- {"fim": true}\\n                 ou  {"erro": "..."}\\n

A voz e o modelo são PESSOAIS (ESCOPO §4): ficam fora do git, em
~/.local/share/jarvis/voz-friday.

    servidor_friday.py [--pasta ~/.local/share/jarvis/voz-friday] [--modelo friday-emilia-v1]
                       [--ref limpa1] [--nfe 12]
"""
from __future__ import annotations

import argparse
import ctypes
import glob
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
import torch
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


PRONUNCIA: list[tuple[re.Pattern, str]] = []


def carregar_pronuncia(arquivo: Path) -> None:
    """`errado = certo` por linha (# comenta). Recarrega a cada fala: dá para
    acrescentar palavra sem reiniciar o servidor."""
    PRONUNCIA.clear()
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        if "=" in linha and not linha.lstrip().startswith("#"):
            errado, certo = (x.strip().lower() for x in linha.split("=", 1))
            if errado and certo:
                PRONUNCIA.append((re.compile(rf"(?<!\w){re.escape(errado)}(?!\w)"), certo))


def normalizar(texto: str) -> str:
    """O modelo PT-BR quer minúsculas, número por extenso e as trocas do
    dicionário de pronúncia."""
    t = re.sub(r"[*_`#>]+", "", texto)
    t = re.sub(r"(\d+)h(\d+)", lambda m: f"{m[1]} e {m[2]}", t)
    t = re.sub(r"(\d+)%", r"\1 por cento", t)
    t = re.sub(r"\d+", lambda m: num2words(int(m[0]), lang="pt_BR"), t)
    t = " ".join(t.lower().split())
    for errado, certo in PRONUNCIA:
        t = errado.sub(certo, t)
    return t


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
    novo = np.asarray(call(man, "Get resynthesis (overlap-add)").values[0], dtype=np.float32)[: len(audio)]
    # Só o fim vem da ressíntese; antes dele, o áudio original (a ressíntese
    # inteira deixava a frase toda um pouco áspera: o Léo preferiu a versão
    # sem acabamento, 25/10/2026). Emenda cruzada de 40 ms.
    corte = int(max(0.0, ini - 0.05) * sr)
    n = min(int(0.04 * sr), len(novo) - corte)
    saida = audio.copy()
    rampa = np.linspace(0, 1, n, dtype=np.float32)
    saida[corte:corte + n] = audio[corte:corte + n] * (1 - rampa) + novo[corte:corte + n] * rampa
    saida[corte + n:len(novo)] = novo[corte + n:]
    return saida


def carregar_whisper():
    """O faster-whisper (ctranslate2) quer o CUDA 12 que a venv da voz não
    tem: carrega as bibliotecas da venv do Jarvis antes (como o
    jarvis/cuda_setup.py faz lá)."""
    base = Path.home() / "Projetos/Jarvis/.venv/lib/python3.12/site-packages/nvidia"
    for padrao in ("cublas/lib/libcublasLt.so.12", "cublas/lib/libcublas.so.12", "cudnn/lib/libcudnn*.so.9"):
        for so in sorted(glob.glob(str(base / padrao))):
            ctypes.CDLL(so, mode=ctypes.RTLD_GLOBAL)
    from faster_whisper import WhisperModel
    return WhisperModel("large-v3-turbo", device="cuda", compute_type="int8")


_INTERJEICOES = {"hmm", "hum", "ahn", "aham", "uhum", "ué", "eita", "opa", "oba", "nossa"}
_IGUAIS = {"para": "pra", "está": "tá", "estou": "tô", "hum": "hmm", "hm": "hmm", "um": "hmm"}


def _palavras(texto: str) -> list[str]:
    return [_IGUAIS.get(p, p) for p in re.findall(r"[^\W\d_]+", texto.lower())]


def _bate(a: str, b: str) -> bool:
    """Tolerante com o que o próprio Whisper erra (diminutivo, gênero):
    mesma palavra ou mesmo começo de 4 letras."""
    return a == b or (len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4])


def defeitos(alvo_texto: str, ouvido_texto: str) -> int:
    """2 por palavra inventada no começo + 1 por palavra (de 3+ letras) que faltou."""
    alvo, ouvido = _palavras(alvo_texto), _palavras(ouvido_texto)
    if not alvo:
        return 0
    if not ouvido:
        return 9
    inventada = not any(_bate(ouvido[0], p) for p in alvo[:2])
    # Interjeição ("hmm", "ah") o Whisper não escreve: não conta como faltando.
    faltou = sum(1 for p in alvo if len(p) >= 3 and p not in _INTERJEICOES and not any(_bate(p, o) for o in ouvido))
    return 2 * inventada + faltou


# O que a Friday fala sempre igual: pronto desde a subida.
FIXAS = ["oi, chefinho!", "tá bom!", "parei.", "pausei.", "voltando!", "próxima!", "anterior.", "prontinho!"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pasta", default=str(Path.home() / ".local/share/jarvis/voz-friday"))
    # Só as 2 últimas versões boas ficam guardadas (pedido do Léo, 25/10/2026):
    # v1 = a aprovada (24/10), v2 = treinada com os recortes limpos (25/10).
    p.add_argument("--modelo", default="friday-emilia-v1")
    p.add_argument("--ref", default="limpa1")
    p.add_argument("--socket", default=os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "jarvis-friday.sock"))
    p.add_argument("--nfe", type=int, default=12)
    # Sem o acabamento (corte, pergunta, volume): só para comparar de ouvido.
    p.add_argument("--cru", action="store_true")
    # Testes de 25/10 (o Léo ouviu palavras cortadas no começo e no fim):
    # sem o corte do "sonzinho" e com folga de duração (segundos a mais).
    p.add_argument("--sem-corte-inicio", action="store_true")
    p.add_argument("--folga", type=float, default=0.0)
    # Gerar e conferir com o Whisper: quantas tentativas no máximo (1 = não confere).
    p.add_argument("--tentativas", type=int, default=3)
    a = p.parse_args()

    inicio = time.monotonic()
    pasta = Path(a.pasta)
    carregar_pronuncia(pasta / "pronuncia.txt")
    tts = F5TTS(model="F5TTS_Base", ckpt_file=str(pasta / f"modelo/{a.modelo}.safetensors"),
                vocab_file=str(pasta / "modelo/vocab.txt"), device="cuda")
    # A referência é preparada uma vez só (antes, a cada frase).
    arq, ref_texto = utils_infer.preprocess_ref_audio_text(
        str(pasta / f"ref/{a.ref}.wav"), normalizar((pasta / f"ref/{a.ref}.txt").read_text()), show_info=lambda *_: None)
    ref = torchaudio.load(arq)
    whisper = carregar_whisper() if a.tentativas > 1 else None
    ref_quadros = ref[0].shape[-1] // 256
    ref_bytes = len(ref_texto.encode("utf-8"))

    def duracao(chave: str) -> float | None:
        """A conta do F5 (referência + texto proporcional) mais a folga fixa."""
        if a.folga <= 0:
            return None
        gen = len(chave.encode("utf-8"))
        return (ref_quadros + int(ref_quadros / ref_bytes * gen) + int(a.folga * 24000 / 256)) * 256 / 24000

    def tirar_silencio_do_fim(audio: np.ndarray, sr: int) -> np.ndarray:
        q = int(0.01 * sr)
        env = np.array([np.sqrt(np.mean(audio[i:i + q] ** 2)) for i in range(0, len(audio) - q, q)])
        voz = np.where(env > env.max() * 0.03)[0]
        return audio[: min(len(audio), (voz[-1] + 1) * q + int(0.15 * sr))] if len(voz) else audio

    guardadas: OrderedDict[str, bytes] = OrderedDict()
    receita = hashlib.sha1(f"friday|{a.ref}|{a.nfe}|{a.modelo}|{'cru' if a.cru else 'v2'}|{a.sem_corte_inicio}|{a.folga}|{a.tentativas}".encode()).hexdigest()[:12]
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
        melhor = None
        for tentativa in range(max(1, a.tentativas)):
            torch.manual_seed(int.from_bytes(os.urandom(4), "little"))
            wav, taxa, _ = next(utils_infer.infer_batch_process(ref, ref_texto, [chave], tts.ema_model, tts.vocoder,
                                                                nfe_step=a.nfe, fix_duration=duracao(chave), device="cuda"))
            bruto = np.asarray(wav, dtype=np.float32)
            if whisper is None:
                melhor = (0, bruto)
                break
            ouvir = tirar_pedacinho(bruto, taxa) if not (a.cru or a.sem_corte_inicio) else bruto
            a16 = np.interp(np.arange(0, len(ouvir), taxa / 16000), np.arange(len(ouvir)), ouvir).astype(np.float32)
            ouvido = " ".join(x.text for x in whisper.transcribe(a16, language="pt", beam_size=1,
                                                                   condition_on_previous_text=False)[0])
            nota = defeitos(frase, ouvido)
            print(f"[{tentativa + 1}] {nota} defeito(s): {frase!r} -> {ouvido.strip()!r}", flush=True)
            if melhor is None or nota < melhor[0]:
                melhor = (nota, bruto)
            if nota == 0:
                break
        audio = melhor[1]
        if a.cru:
            pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes()
        else:
            if not a.sem_corte_inicio:
                audio = tirar_pedacinho(audio, taxa)
            if a.folga > 0:
                audio = tirar_silencio_do_fim(audio, taxa)
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
                carregar_pronuncia(pasta / "pronuncia.txt")
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
