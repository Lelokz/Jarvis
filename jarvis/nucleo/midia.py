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

import os
import re
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ..config import Midia as ConfigMidia
from .atalhos import normalizar

# Comandos de mídia crus: a fala INTEIRA é o comando, sem objeto nenhum.
#
# Estes não passam pelo modelo, e a razão é medida. Com o núcleo em 9 funções,
# "Para!" caía em nada 5/5 e "Dá play." ia para `tocar` 5/5, perguntando "qual
# música?" quando o Léo só queria despausar. Pôr a reivindicação na descrição
# do `midia` — a lição do "procura" — consertou "Continua." e "Dá play.", mas
# "Para!" resistiu, 1/5: **"para" é preposição em português**, e o modelo não
# consegue lê-la como imperativo isolado. Não é problema de instrução.
#
# É o mesmo desenho do `_estreitar`, que também não passa pelo LLM: texto
# casado contra uma lista fechada, mais rápido e sem nada que possa errar. E
# diminui a superfície do modelo em vez de aumentar — estas falas, que são as
# mais frequentes de todas, param de chegar nele. Medido nos logs reais: 0,46s
# de núcleo em média, quase tudo o modelo decidindo.
#
# `volta` NÃO entra, de propósito. Ele vai para `desfazer` 5/5 hoje, e está
# certo: "volta atrás" é a frase da Etapa 5. Pôr aqui roubaria o desfazer de
# forma determinística.
COMANDOS_CRUS = {
    "para": "pausar",
    "pare": "pausar",
    "parar": "pausar",
    "parou": "pausar",
    "pausa": "pausar",
    "pause": "pausar",
    "pausar": "pausar",
    "continua": "continuar",
    "continue": "continuar",
    "continuar": "continuar",
    "segue": "continuar",
    "play": "continuar",
    "despausa": "continuar",
    "retoma": "continuar",
    "proxima": "proxima",
    "proximo": "proxima",
    "pula": "proxima",
    "anterior": "anterior",
}


# Como o Léo diz QUAL player, quando há mais de um tocando.
#
# Sem isto ele não tinha como escolher: com o Brave e o mpv tocando, "pausa"
# sempre pegava o mpv, e o Brave só era alcançado quando o mpv já estava
# pausado — o que é a fila esvaziando, não escolha. E para voltar o Brave não
# havia jeito nenhum.
#
# "do navegador" foi proposto e o Léo cortou: ele usa o Brave há mais de um ano
# e não vai trocar, e sinônimo a mais é superfície a mais. É a lição da rodada
# do "para", aplicada por ele.
QUALIFICADORES = {
    "brave": "brave",
    "aba": "brave",
    "youtube": "brave",
    "computador": "nosso",
    "pc": "nosso",
    "player": "nosso",
    "tua": "nosso",
    "sua": "nosso",
    "pos": "nosso",  # "a que você pôs"
}


@dataclass(frozen=True)
class ComandoCru:
    acao: str
    qual: str | None = None  # "brave" | "nosso" | None = regra de hoje


# Enfeites de pedido educado. Tirados só DEPOIS de o casamento direto falhar,
# e só para ver se o que sobra é um comando sozinho.
#
# Medido: a família "dá play" quebrava em 7 de 13 variantes, virando volume com
# valores inventados — 'Tu pode dar play?' dava volume='mais' em 6 de 8. A
# diferença entre as que funcionavam e as que não era só o embrulho: "Dá play."
# acertava e "Pode dar play agora." não. Tirar o embrulho resolve a família
# inteira de uma vez, em vez de enumerar formas.
_ENFEITES = frozenset(
    {
        "pode", "podes", "poderia", "por", "favor", "agora", "ai", "la",
        "tu", "voce", "me", "dar", "da", "ja", "entao", "so", "af", "que",
    }
)


def comando_cru(falado: str) -> ComandoCru | None:
    """A ação, quando a fala INTEIRA é um comando de mídia sem objeto.

    O casamento é contra a fala toda, normalizada — nunca por substring. É isso
    que mantém "Renomeia o relatório **para** proposta" fora daqui: a chave é
    a frase inteira, não uma palavra dentro dela.

    O `normalizar()` já resolve caixa, acento e pontuação, e ainda tira "dá"
    como supérflua, então "Dá play." chega aqui como "play". A caixa importa
    mais do que parece: foi ela que decidiu o `'não'` contra `'Não'` na Etapa 4
    e o `'continua'` contra `'Continua.'` aqui — e o Whisper sempre capitaliza
    a primeira palavra.
    """
    chave = normalizar(falado)
    direto = COMANDOS_CRUS.get(chave)
    if direto is not None:
        return ComandoCru(direto)

    # Tira o embrulho educado e vê o que sobra.
    #
    # UMA palavra: é o comando sozinho. "pode dar play agora" -> "play".
    # DUAS: pode ser comando + qual player. "pausa a do brave" -> pausa, brave.
    #
    # Exigir uma ou duas é o que mantém "para a música" fora daqui — "musica"
    # não é qualificador, então o par não casa e a frase vai para o modelo, que
    # acerta essa forma. E "renomeia o relatório para proposta" sobra inteira.
    resto = [p for p in chave.split() if p not in _ENFEITES]
    if len(resto) == 1:
        acao = COMANDOS_CRUS.get(resto[0])
        return ComandoCru(acao) if acao else None
    if len(resto) == 2:
        for i, outro in ((0, 1), (1, 0)):
            acao = COMANDOS_CRUS.get(resto[i])
            qual = QUALIFICADORES.get(resto[outro])
            if acao and qual:
                return ComandoCru(acao, qual)
    return None


MPRIS_CAMINHO = "/org/mpris/MediaPlayer2"

# O PID do mpv que NÓS criamos. Guardamos o PID, e não o nome do barramento,
# porque o nome mente: só o primeiro mpv de uma sessão ganha
# "org.mpris.MediaPlayer2.mpv"; os seguintes viram "mpv.instance{PID}". A
# versão anterior gravava o nome curto fixo e comparava com `startswith`, o que
# fazia "nosso" significar "qualquer mpv" — e o desempate pegava o mais velho.
# No teste do Léo isso apareceu inteiro: o primeiro "pausa" pausou a música
# antiga, e foi preciso um segundo "pausa" para calar a que ele tinha acabado
# de pedir.
#
# O D-Bus responde qual PID é dono de cada nome, então o PID é identidade de
# verdade e não precisa de adivinhação.
_nosso_pid: int | None = None
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


def _soltar(comando: list[str]) -> int | None:
    """Dispara, desgruda e devolve o PID.

    `start_new_session` desgruda o processo: fechar o Jarvis não pode calar a
    música. O PID volta porque é a única identidade confiável do player que
    acabamos de criar.
    """
    p = subprocess.Popen(
        comando,
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return p.pid


def _dono(nome: str) -> int | None:
    """De qual processo é este nome do barramento."""
    saida = _gdbus(
        [
            "call", "--session",
            "--dest", "org.freedesktop.DBus",
            "--object-path", "/org/freedesktop/DBus",
            "--method", "org.freedesktop.DBus.GetConnectionUnixProcessID",
            nome,
        ]
    )
    if not saida:
        return None
    achado = re.search(r"uint32 (\d+)", saida)
    return int(achado.group(1)) if achado else None


def nosso_player() -> str | None:
    """O nome do barramento do mpv que nós criamos, se ele ainda vive."""
    if _nosso_pid is None:
        return None
    for nome in players():
        if _dono(nome) == _nosso_pid:
            return nome
    return None


def encerrar_nosso() -> bool:
    """Encerra o mpv que NÓS criamos. Nunca toca em outro player.

    A identidade é o PID que guardamos, então o Brave do Léo e qualquer mpv que
    ele tenha aberto na mão ficam de fora por construção — não há nome nem
    prefixo envolvido na decisão.
    """
    global _nosso_pid
    if _nosso_pid is None:
        return False
    try:
        os.kill(_nosso_pid, signal.SIGTERM)
        encerrado = True
    except (ProcessLookupError, PermissionError, OSError):
        encerrado = False
    _nosso_pid = None
    return encerrado


def _posicao(player: str) -> int | None:
    """A posição em microssegundos. O gdbus devolve "int64 32671833"."""
    bruto = _propriedade(player, "Position")
    if bruto is None:
        return None
    achado = re.search(r"(-?\d+)", bruto)
    return int(achado.group(1)) if achado else None


def _esperar_o_som(pid: int, segundos: float) -> bool:
    """Espera a POSIÇÃO andar. É a única prova de que saiu som.

    `PlaybackStatus` não serve, e isso é medido: o mpv entra no barramento em
    0,45s já dizendo "Playing" e a posição só sai do zero por volta de 6s. É o
    mesmo `CanGoNext` da Etapa 3 — não confiar no que o player declara, e sim
    observar. Sem isto o Jarvis anunciava "Tocando" antes de existir som, e o
    Léo não tinha como saber se tinha tocado.
    """
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        for nome in players():
            if _dono(nome) != pid:
                continue
            pos = _posicao(nome)
            if pos is not None and pos > 0:
                return True
        time.sleep(0.25)
    return False


def url_de_audio(video: Video, cfg: ConfigMidia) -> str | None:
    """A URL direta do áudio, resolvida por nós.

    Sem isto o yt-dlp roda DUAS vezes: uma nossa, para achar o vídeo, e outra
    dentro do mpv, pelo `ytdl_hook`. A segunda é invisível e custa ~6s — é ela
    que fazia o som demorar a sair enquanto o Jarvis já tinha dito "Tocando".
    Resolvendo aqui, custa ~2,5s que a gente vê, e o mpv começa quase na hora.

    None quando não dá: quem chama cai para a URL do YouTube, que ainda toca —
    só demora mais e é menos observável.
    """
    try:
        saida = subprocess.run(
            [cfg.comando_ytdlp, "--no-warnings", "-f", "bestaudio",
             "--get-url", video.url],
            capture_output=True, text=True, timeout=cfg.segundos_busca,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    linha = saida.stdout.strip().splitlines()
    return linha[0] if linha and linha[0].startswith("http") else None


def tocar_audio(video: Video, cfg: ConfigMidia) -> Resultado:
    """mpv tocando só o áudio: sem janela, sem aba, só som.

    Substitui o que nós mesmos tínhamos posto para tocar, em vez de somar. No
    teste do Léo, somar produziu duas músicas em cima da outra, três processos
    órfãos vivos por 20 minutos, e um "pausa" que precisou ser dito duas vezes
    para calar o que ele pediu uma vez.

    **Só encerra o que é nosso**, identificado por PID. O Brave dele e qualquer
    mpv aberto na mão ficam de fora — a lição da Etapa 3, quando eu pausei a
    sessão real dele num teste.
    """
    global _nosso_pid
    if shutil.which(cfg.comando_mpv) is None:
        return Resultado(
            False,
            f"O {cfg.comando_mpv} não está instalado. "
            "Instale com: sudo apt install mpv",
        )

    direta = url_de_audio(video, cfg)
    comando = [cfg.comando_mpv, "--no-video", "--really-quiet"]
    if direta:
        comando.append(direta)
    else:
        # Sem a URL direta, o mpv resolve por dentro: toca, mas demora mais.
        comando.append(f"--script-opts=ytdl_hook-ytdl_path={cfg.comando_ytdlp}")
        comando.append(video.url)

    encerrar_nosso()
    try:
        pid = _soltar(comando)
    except OSError as e:
        return Resultado(False, f"Não consegui tocar: {e}")
    _nosso_pid = pid

    detalhe = {"video": video.id, "pid": pid, "url_direta": bool(direta)}
    if not _esperar_o_som(pid, cfg.segundos_para_o_som):
        # Não saiu som. Encerrar é melhor que deixar um processo mudo vivo —
        # foi assim que três mpv ficaram pendurados na sessão do Léo.
        encerrar_nosso()
        return Resultado(False, "", {**detalhe, "som": False})

    return Resultado(True, f"Tocando {video.titulo}.", {**detalhe, "som": True})


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


def _escolher_player(qual: str | None = None) -> str | None:
    """Quem recebe o comando quando há mais de um player aberto.

    Quando o Léo DIZ qual, é ele quem manda — e se o pedido não existe, quem
    chama avisa em vez de agir no outro. Escolher errado em silêncio é pior
    que dizer que não achou.

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

    if qual == "nosso":
        return nosso_player()
    if qual == "brave":
        candidatos = [p for p in disponiveis if "brave" in p.lower()]
        return candidatos[0] if candidatos else None

    nosso = nosso_player()
    nossos = [p for p in disponiveis if p == nosso]
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


NOME_FALAVEL = {"brave": "no Brave", "nosso": "no computador"}


def controlar(acao: str, qual: str | None = None) -> Resultado:
    """pausar | continuar | proxima | anterior — no player que estiver ativo.

    `qual` vem do que o Léo falou: "pausa a do Brave", "dá play na do
    computador". Sem `qual`, vale a regra de sempre — o que o Jarvis iniciou
    ganha.
    """
    metodos = {
        "pausar": ("Pause", "CanPause", "Pausei."),
        "continuar": ("Play", "CanPlay", "Voltando."),
        "proxima": ("Next", "CanGoNext", "Próxima."),
        "anterior": ("Previous", "CanGoPrevious", "Anterior."),
    }
    if acao not in metodos:
        return Resultado(False, f"Não sei fazer {acao}.")

    player = _escolher_player(qual)
    if player is None:
        onde = NOME_FALAVEL.get(qual or "")
        if onde:
            return Resultado(False, f"Não tem nada tocando {onde}.")
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
