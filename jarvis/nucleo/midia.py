"""Tocar música e controlar o que já está tocando.

Duas coisas bem diferentes moram aqui, e a separação é de propósito:

**Tocar** precisa de um alvo — um nome de música. Vai para o `mpv` (só áudio,
sem janela) ou para o navegador, quando o Léo pede "no YouTube".

**Controlar** não tem alvo. Pausar age no que estiver tocando, seja o mpv, um
vídeo no Brave ou o Spotify. Isso é feito por MPRIS, o padrão de D-Bus que todo
player de Linux implementa — e a boa notícia medida antes de planejar: o Brave
**já** expõe MPRIS e o `gdbus` já está instalado, então controlar não custou
dependência nenhuma.

O `yt-dlp` aparece em dois papéis diferentes, e é bom não confundir:
resolver a busca num ID de vídeo (rápido, funciona até na versão velha do apt)
e extrair a URL de áudio (precisa da versão nova — a do apt falha com
"Requested format is not available").
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ..config import Midia as ConfigMidia

MPRIS_CAMINHO = "/org/mpris/MediaPlayer2"

# Quem o Jarvis iniciou por último. Sem isto, o desempate entre dois players
# era alfabético — "brave" antes de "mpv" —, então mandar tocar uma música e
# dizer "pausa" em seguida podia pausar um vídeo do navegador em vez da
# música que ele mesmo acabou de pôr.
_iniciado_por_nos: str | None = None
MPRIS_PLAYER = "org.mpris.MediaPlayer2.Player"


@dataclass(frozen=True)
class Video:
    id: str
    titulo: str
    canal: str
    duracao_s: float

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.id}"


@dataclass(frozen=True)
class Resultado:
    ok: bool
    mensagem: str
    detalhe: dict | None = None


# ---------------------------------------------------------------------------
# achar no YouTube
# ---------------------------------------------------------------------------


def buscar(termo: str, cfg: ConfigMidia) -> Video | None:
    """Resolve um termo no primeiro vídeo do YouTube.

    `--flat-playlist` de propósito: pula a extração de formatos, que é a parte
    cara e a que quebra em versão velha do yt-dlp. Medido em ~1,6s.
    """
    if shutil.which(cfg.comando_ytdlp) is None:
        return None
    try:
        saida = subprocess.run(
            [
                cfg.comando_ytdlp,
                "--no-warnings",
                "--flat-playlist",
                "--print",
                "%(id)s\t%(title)s\t%(channel)s\t%(duration)s",
                f"ytsearch1:{termo}",
            ],
            capture_output=True,
            text=True,
            timeout=cfg.segundos_busca,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    linha = saida.stdout.strip().splitlines()
    if not linha:
        return None
    partes = linha[0].split("\t")
    if len(partes) < 4 or not partes[0]:
        return None
    try:
        duracao = float(partes[3])
    except ValueError:
        duracao = 0.0
    return Video(id=partes[0], titulo=partes[1], canal=partes[2], duracao_s=duracao)


# ---------------------------------------------------------------------------
# tocar
# ---------------------------------------------------------------------------


def _soltar(comando: list[str]) -> None:
    """Dispara e desgruda — fechar o Jarvis não pode calar a música."""
    subprocess.Popen(
        comando,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def tocar_audio(video: Video, cfg: ConfigMidia) -> Resultado:
    """mpv tocando só o áudio: sem janela, sem aba, só som."""
    if shutil.which(cfg.comando_mpv) is None:
        return Resultado(
            False,
            f"O {cfg.comando_mpv} não está instalado. "
            "Instale com: sudo apt install mpv",
        )
    comando = [
        cfg.comando_mpv,
        "--no-video",
        "--really-quiet",
        # Um nome de instância MPRIS estável facilita achar o player depois.
        f"--script-opts=ytdl_hook-ytdl_path={cfg.comando_ytdlp}",
        video.url,
    ]
    try:
        _soltar(comando)
    except OSError as e:
        return Resultado(False, f"Não consegui tocar: {e}")
    global _iniciado_por_nos
    _iniciado_por_nos = "org.mpris.MediaPlayer2.mpv"
    return Resultado(True, f"Tocando {video.titulo}.", {"video": video.id})


def tocar_navegador(video: Video, cfg: ConfigMidia) -> Resultado:
    """Abre o vídeo no navegador, para quando o Léo quer ver e não só ouvir."""
    if shutil.which(cfg.comando_navegador) is None:
        return Resultado(
            False, f"O {cfg.comando_navegador} não está instalado."
        )
    try:
        _soltar([cfg.comando_navegador, video.url])
    except OSError as e:
        return Resultado(False, f"Não consegui abrir: {e}")
    return Resultado(True, f"Abrindo {video.titulo} no YouTube.", {"video": video.id})


# ---------------------------------------------------------------------------
# controlar quem estiver tocando (MPRIS)
# ---------------------------------------------------------------------------


def _gdbus(args: list[str], timeout: float = 5.0) -> str | None:
    try:
        saida = subprocess.run(
            ["gdbus", *args], capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return saida.stdout.strip() if saida.returncode == 0 else None


def players() -> list[str]:
    """Quem está no barramento agora. Vazio = nada tocando."""
    saida = _gdbus(
        [
            "call", "--session",
            "--dest", "org.freedesktop.DBus",
            "--object-path", "/org/freedesktop/DBus",
            "--method", "org.freedesktop.DBus.ListNames",
        ]
    )
    if not saida:
        return []
    return sorted(
        {p for p in saida.replace("'", " ").split() if p.startswith("org.mpris.")}
    )


def _propriedade(player: str, nome: str) -> str | None:
    saida = _gdbus(
        [
            "call", "--session", "--dest", player,
            "--object-path", MPRIS_CAMINHO,
            "--method", "org.freedesktop.DBus.Properties.Get",
            MPRIS_PLAYER, nome,
        ]
    )
    if not saida:
        return None
    # O gdbus devolve algo como (<'Playing'>,) ou (<true>,)
    return saida.strip("(),<> ").strip("'")


def _escolher_player() -> str | None:
    """Quem recebe o comando quando há mais de um player aberto.

    A ordem foi pensada em cima do que surpreende menos:

      1. tocando E iniciado por nós — a música que o Jarvis acabou de pôr
      2. qualquer um tocando — o Léo fala do som que ele ouve
      3. iniciado por nós, mesmo pausado — "continua" depois de "pausa"
      4. o primeiro que houver

    O alfabeto não pode decidir isto: "brave" vem antes de "mpv", então o
    desempate ingênuo pausaria um vídeo do navegador em vez da música.
    """
    disponiveis = players()
    if not disponiveis:
        return None

    nossos = [p for p in disponiveis if _iniciado_por_nos and p.startswith(_iniciado_por_nos)]
    tocando = [p for p in disponiveis if _propriedade(p, "PlaybackStatus") == "Playing"]

    for candidato in (
        [p for p in nossos if p in tocando],
        tocando,
        nossos,
        disponiveis,
    ):
        if candidato:
            return candidato[0]
    return None


def controlar(acao: str) -> Resultado:
    """pausar | continuar | proxima | anterior — no player que estiver ativo."""
    metodos = {
        "pausar": ("Pause", "CanPause", "Pausei."),
        "continuar": ("Play", "CanPlay", "Voltando."),
        "proxima": ("Next", "CanGoNext", "Próxima."),
        "anterior": ("Previous", "CanGoPrevious", "Anterior."),
    }
    if acao not in metodos:
        return Resultado(False, f"Não sei fazer {acao}.")

    player = _escolher_player()
    if player is None:
        return Resultado(False, "Não tem nada tocando.")

    metodo, capacidade, confirmacao = metodos[acao]

    # `CanGoNext` é false num vídeo solto do YouTube — só playlist tem próxima.
    # Chamar assim mesmo falharia calado; melhor dizer que não dá.
    if _propriedade(player, capacidade) == "false":
        nome = player.rsplit(".", 1)[0].replace("org.mpris.MediaPlayer2.", "")
        return Resultado(False, f"O que está tocando no {nome} não tem {acao}.")

    # Para trocar de faixa, guardamos o que está tocando ANTES: o
    # `CanGoNext` não é confiável. O mpv responde `true` mesmo com um vídeo
    # só na fila, e aí o Next não faz nada — e dizer "Próxima." sem nada ter
    # mudado é mentir para o Léo. O Brave reporta `false` corretamente, mas
    # não dá para depender disso.
    trocando = acao in ("proxima", "anterior")
    antes = _faixa(player) if trocando else None

    ok = _gdbus(
        [
            "call", "--session", "--dest", player,
            "--object-path", MPRIS_CAMINHO,
            "--method", f"{MPRIS_PLAYER}.{metodo}",
        ]
    )
    if ok is None:
        return Resultado(False, f"Não consegui {acao}.")

    if trocando:
        time.sleep(0.6)  # o player precisa de um instante para trocar
        if _faixa(player) == antes:
            rotulo = "próxima" if acao == "proxima" else "anterior"
            return Resultado(False, f"Não tem {rotulo} — é só isso na fila.")

    return Resultado(True, confirmacao, {"player": player, "metodo": metodo})


def _faixa(player: str) -> str | None:
    """Identidade do que está tocando — para saber se o Next mudou algo."""
    return _gdbus(
        [
            "call", "--session", "--dest", player,
            "--object-path", MPRIS_CAMINHO,
            "--method", "org.freedesktop.DBus.Properties.Get",
            MPRIS_PLAYER, "Metadata",
        ]
    )


def o_que_esta_tocando() -> str | None:
    """Título do que toca agora, para o Jarvis poder mencionar."""
    player = _escolher_player()
    if player is None:
        return None
    saida = _gdbus(
        [
            "call", "--session", "--dest", player,
            "--object-path", MPRIS_CAMINHO,
            "--method", "org.freedesktop.DBus.Properties.Get",
            MPRIS_PLAYER, "Metadata",
        ]
    )
    if not saida or "xesam:title" not in saida:
        return None
    depois = saida.split("xesam:title", 1)[1]
    for pedaco in depois.split("'"):
        if len(pedaco) > 2 and not pedaco.startswith((":", ",", " <")):
            return pedaco
    return None
