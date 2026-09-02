#!/usr/bin/env python3
"""Jarvis — Etapa 0: esqueleto de voz.

Ouve, transcreve e repete de volta. Zero ações, zero LLM, zero wake word.

Existe para responder duas perguntas, e só elas:
  1. A latência do ciclo completo é tolerável nesta máquina?
  2. O Whisper transcreve o português do Léo de forma confiável?

Se a resposta a qualquer uma for "não", a arquitetura do ESCOPO muda antes de
alguém escrever a Etapa 1.
"""

from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from jarvis import config, cronometro, microfone, tts
from jarvis.cronometro import Tempos
from jarvis.registro import Registrador
from jarvis.stt import ErroDeCuda, Transcritor
from jarvis.vad import DetectorDeFala

FRASE_DO_AUTOTESTE = "Um dois três, testando o esqueleto de voz do Jarvis."


# ---------------------------------------------------------------------------
# apoio
# ---------------------------------------------------------------------------


def _vram() -> str:
    try:
        saida = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        usada, total = saida.stdout.strip().splitlines()[0].split(",")
        return f"{int(usada) / 1024:.1f} GB / {int(total) / 1024:.1f} GB"
    except Exception:
        return "(nvidia-smi indisponível)"


def _reamostrar(audio: np.ndarray, de: int, para: int) -> np.ndarray:
    """Reamostragem linear, só para o autoteste.

    O Piper entrega 22050Hz e o Whisper quer 16000Hz. Interpolação linear é
    grosseira, mas aqui o objetivo é provar que a cadeia liga — não medir
    qualidade de áudio.
    """
    if de == para:
        return audio.astype(np.float32)
    n = int(round(len(audio) * para / de))
    origem = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
    destino = np.linspace(0.0, 1.0, num=n, endpoint=False)
    return np.interp(destino, origem, audio).astype(np.float32)


def _normalizar(texto: str) -> str:
    return re.sub(r"[^\w\s]", "", texto.lower()).strip()


# ---------------------------------------------------------------------------
# modos
# ---------------------------------------------------------------------------


def listar_dispositivos() -> int:
    entradas = [d for d in microfone.listar_dispositivos() if d.canais_entrada]
    saidas = [d for d in microfone.listar_dispositivos() if d.canais_saida]

    print("\nENTRADAS (microfone)")
    for d in entradas:
        marca = " ← padrão do sistema" if d.padrao_entrada else ""
        print(f"  [{d.indice:>2}] {d.nome}{marca}")
        print(f"       {d.canais_entrada} canal(is) · {d.taxa_padrao:.0f} Hz")

    print("\nSAÍDAS (alto-falante)")
    for d in saidas:
        marca = " ← padrão do sistema" if d.padrao_saida else ""
        print(f"  [{d.indice:>2}] {d.nome}{marca}")

    print(
        "\nPara fixar um deles, ponha um trecho do nome em dispositivo_entrada"
        "\nou dispositivo_saida no config.toml.\n"
    )
    return 0


def autoteste(cfg: config.Config) -> int:
    """Prova a cadeia sem depender do microfone.

    Sintetiza uma frase no Piper, empurra o áudio pelo VAD e pelo Whisper e
    confere se o texto volta parecido. Se isto passa, o que sobrar de problema
    é de microfone ou de acústica — não de modelo nem de CUDA.
    """
    print("\nAUTOTESTE (sem microfone)\n" + "─" * cronometro.LARGURA)

    print("  carregando Piper...", flush=True)
    voz = tts.criar_voz(cfg.tts, cfg.dir_vozes)
    trechos = list(voz.sintetizar(FRASE_DO_AUTOTESTE))
    if not trechos:
        print("  FALHOU: o Piper não devolveu áudio.")
        return 1
    taxa_piper = trechos[0].taxa
    pcm = b"".join(t.pcm for t in trechos)
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    print(f"  Piper OK — {len(audio) / taxa_piper:.2f}s a {taxa_piper}Hz")

    print("  carregando Whisper...", flush=True)
    try:
        transcritor = Transcritor(cfg.stt)
    except ErroDeCuda as e:
        print(f"\n  FALHOU no CUDA:\n{e}\n")
        return 1
    print(f"  Whisper OK — carregou em {transcritor.segundos_de_carga:.2f}s")
    print(f"  aquecendo... {transcritor.aquecer():.2f}s")

    audio_16k = _reamostrar(audio, taxa_piper, cfg.audio.taxa_amostragem)

    # Passa pelo VAD do jeito real: em blocos, como viria do microfone.
    detector = DetectorDeFala(cfg.vad, cfg.audio.taxa_amostragem)
    pcm_16k = (audio_16k * 32767).astype(np.int16).tobytes()
    passo = detector.bytes_por_bloco
    silencio = b"\x00" * passo
    blocos = [pcm_16k[i : i + passo] for i in range(0, len(pcm_16k), passo)]
    blocos = [b for b in blocos if len(b) == passo]
    # Silêncio na frente e atrás para o VAD ter como abrir e fechar sozinho.
    margem = max(1, round(cfg.vad.silencio_final_ms / 1000 / detector.duracao_bloco_s)) + 2
    sequencia = [silencio] * 3 + blocos + [silencio] * margem

    segmento = None
    for bloco in sequencia:
        resultado = detector.processar(bloco)
        if resultado is not None:
            segmento = resultado
            break

    if segmento is None:
        print("\n  FALHOU: o VAD não reconheceu fala no áudio do próprio Piper.")
        print("  Isso aponta para o limiar do VAD, não para o microfone.")
        return 1
    print(
        f"  VAD OK — segmento de {segmento.duracao_total_s:.2f}s "
        f"({segmento.duracao_fala_s:.2f}s de fala)"
    )

    t = transcritor.transcrever(segmento.audio)
    parecenca = difflib.SequenceMatcher(
        None, _normalizar(FRASE_DO_AUTOTESTE), _normalizar(t.texto)
    ).ratio()

    print("─" * cronometro.LARGURA)
    print(f'  falado:       "{FRASE_DO_AUTOTESTE}"')
    print(f'  transcrito:   "{t.texto}"')
    print(f"  parecença:    {parecenca:.0%}   (STT em {t.segundos:.2f}s)")
    print("─" * cronometro.LARGURA)

    if parecenca >= 0.70:
        print("  PASSOU — a cadeia TTS → VAD → STT está de pé.\n")
        return 0
    print("  ATENÇÃO — transcrição muito diferente do esperado.")
    print("  A cadeia roda, mas vale olhar o modelo/idioma antes de seguir.\n")
    return 1


def _partida(rotulo: str, detalhe: str, segundos: float | None = None) -> None:
    """Linha do relatório de custos de partida (pagos uma vez, na subida)."""
    tempo = f"{segundos:>6.2f} s" if segundos is not None else ""
    print(f"  {rotulo:<14} {detalhe:<32}{tempo}")


def conversar(cfg: config.Config) -> int:
    print(f"\n{cfg.persona.nome} — Etapa 0 (esqueleto de voz)")

    try:
        indice_entrada = microfone.resolver(cfg.audio.dispositivo_entrada, entrada=True)
        indice_saida = microfone.resolver(cfg.audio.dispositivo_saida, entrada=False)
    except ValueError as e:
        print(f"\n{e}\n", file=sys.stderr)
        return 1
    _partida("microfone", microfone.nome_do_dispositivo(indice_entrada, entrada=True))

    inicio = time.monotonic()
    detector = DetectorDeFala(cfg.vad, cfg.audio.taxa_amostragem)
    _partida("VAD", "Silero via pysilero-vad", time.monotonic() - inicio)

    try:
        transcritor = Transcritor(cfg.stt)
    except ErroDeCuda as e:
        print(f"\nCUDA não subiu:\n{e}\n")
        return 1
    _partida("Whisper", transcritor.descricao, transcritor.segundos_de_carga)
    _partida("aquecimento", "(1ª inferência, descartada)", transcritor.aquecer())

    try:
        voz = tts.criar_voz(cfg.tts, cfg.dir_vozes)
    except FileNotFoundError as e:
        print(f"\n{e}\n")
        return 1
    _partida("Piper", voz.nome, voz.segundos_de_carga)
    _partida("VRAM em uso", _vram())

    registrador = Registrador.criar(cfg)
    resumo = cronometro.Resumo()
    vazias = 0
    guarda_s = cfg.audio.guarda_pos_fala_ms / 1000

    print(f"\n  log: {registrador.caminho_jsonl}")
    if registrador.dir_audio:
        print(f"  áudio: {registrador.dir_audio}/")
    print("\npronto. fale. (ctrl+c encerra e mostra o resumo)\n")

    mic: microfone.Microfone | None = None
    try:
        with microfone.Microfone(
            taxa=cfg.audio.taxa_amostragem,
            amostras_por_bloco=detector.amostras_por_bloco,
            dispositivo=indice_entrada,
        ) as mic:
            while True:
                bloco = mic.ler_bloco()
                if bloco is None:
                    continue

                segmento = detector.processar(bloco)
                if segmento is None:
                    continue

                transcricao = transcritor.transcrever(segmento.audio)
                if not transcricao.texto:
                    # O VAD ouviu algo, o Whisper não achou palavra. Não fala
                    # nada: silêncio é melhor que eco de alucinação.
                    vazias += 1
                    registrador.registrar_descarte(
                        "transcricao vazia",
                        {"duracao_s": round(segmento.duracao_total_s, 3)},
                    )
                    print("  (VAD disparou, Whisper não transcreveu nada)")
                    continue

                # Portão anti-eco: fechado enquanto ele fala.
                mic.fechar_portao()
                try:
                    fala = tts.falar(voz, transcricao.texto, dispositivo=indice_saida)
                finally:
                    time.sleep(guarda_s)
                    mic.abrir_portao()

                tempos = Tempos(
                    duracao_segmento_s=segmento.duracao_total_s,
                    espera_silencio_s=segmento.espera_silencio_s,
                    stt_s=transcricao.segundos,
                    tts_primeiro_s=fala.primeiro_audio_s,
                    tts_total_s=fala.sintese_total_s,
                    reproducao_s=fala.reproducao_s,
                )
                resumo.adicionar(tempos)
                registrador.registrar_frase(
                    segmento=segmento,
                    texto=transcricao.texto,
                    tempos=tempos,
                    idioma=transcricao.idioma,
                    probabilidade_idioma=transcricao.probabilidade_idioma,
                )
                print(cronometro.formatar_bloco(transcricao.texto, tempos))

    except KeyboardInterrupt:
        print("\n")
    finally:
        print(
            resumo.formatar(
                descartados=detector.descartados_curtos, vazias=vazias
            )
        )
        if mic is not None and mic.estouros:
            print(f"  blocos perdidos pelo PortAudio: {mic.estouros}")
        print(f"  medições em {registrador.caminho_jsonl}\n")
    return 0


# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Jarvis — Etapa 0: ouvir, transcrever e repetir."
    )
    parser.add_argument(
        "--listar-dispositivos",
        action="store_true",
        help="mostra os microfones e saídas que o PortAudio enxerga",
    )
    parser.add_argument(
        "--autoteste",
        action="store_true",
        help="testa a cadeia TTS → VAD → STT sem usar o microfone",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="caminho de um config.toml alternativo",
    )
    args = parser.parse_args(argv)

    if args.listar_dispositivos:
        return listar_dispositivos()

    try:
        cfg = config.carregar(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"\n{e}\n", file=sys.stderr)
        return 1

    if args.autoteste:
        return autoteste(cfg)
    return conversar(cfg)


if __name__ == "__main__":
    sys.exit(main())
