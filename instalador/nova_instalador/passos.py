"""Tela 4 do instalador ("Instalação"): o que de fato instala a NOVA.

Cada parte é um Passo. Quando termina, grava `<pasta>/.instalacao/<id>.ok`: se
a internet cair ou o PC desligar, a próxima vez pula o que já foi e recomeça
do passo que parou (os downloads continuam do byte onde pararam).

Tudo de fontes oficiais, conferido pelo sha256 quando é arquivo solto: o código
(GitHub da NOVA), as bibliotecas (PyPI, pelo uv), o ouvido (Whisper, Hugging
Face), o "Hey Jarvis" (openWakeWord), o "Hey Friday" (coleção da comunidade do
Home Assistant), a voz leve (Kokoro), o Claude Code (claude.ai) e, para quem
pode, as vozes dubladas (o Drive do Léo, endereço só no script do convite).
Nada pede senha de administrador.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# O código que veio junto com o instalador (o zip do GitHub).
CODIGO = Path(__file__).resolve().parent.parent.parent

OWW = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/"
KOKORO = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
ARQUIVOS_SOLTOS = {
    # destino dentro de app/ -> (endereço, sha256)
    "modelos-wakeword/melspectrogram.onnx": (OWW + "melspectrogram.onnx", "ba2b0e0f8b7b875369a2c89cb13360ff53bac436f2895cced9f479fa65eb176f"),
    "modelos-wakeword/embedding_model.onnx": (OWW + "embedding_model.onnx", "70d164290c1d095d1d4ee149bc5e00543250a7316b59f31d056cff7bd3075c1f"),
    "modelos-wakeword/hey_jarvis_v0.1.onnx": (OWW + "hey_jarvis_v0.1.onnx", "94a13cfe60075b132f6a472e7e462e8123ee70861bc3fb58434a73712ee0d2cb"),
    "modelos-wakeword/hey_friday_comunidade.onnx": (
        "https://raw.githubusercontent.com/fwartner/home-assistant-wakewords-collection/main/en/hey_friday/hey_Friday!.onnx",
        "a5a51b398426db79bd4a6d058b5928bb2c0cfe946db24a974845652f00dcae57"),
    "vozes/kokoro-v1.0.onnx": (KOKORO + "kokoro-v1.0.onnx", "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5"),
    "vozes/voices-v1.0.bin": (KOKORO + "voices-v1.0.bin", "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"),
}
VOZES_SHA256 = "d64bafe1df9dfb29404c122e48ca823d89ed1267224b90118a683aa9dbcba5bd"
# O que não precisa ir para o PC de quem instala.
# Os modelos vêm pelos passos (vozes/, modelos-wakeword/), e os arquivos pessoais do Léo
# nunca estão no zip do GitHub, mas ficam de fora também se rodar de uma pasta como a dele.
NAO_COPIAR = ("site", "celular", "rascunho", "logs", "medicoes", ".git", "__pycache__", ".venv", "instalador",
              "vozes", "modelos-wakeword", "credenciais_google.json", "token_google.json", "memoria.txt",
              "conversas.jsonl", "conversa-atual.jsonl", "agenda_ical.txt", ".firebase", ".claude")


@dataclass
class Contexto:
    pasta: Path                    # onde instalar (a escolhida na tela 3)
    nvidia: bool                   # placa NVIDIA: bibliotecas CUDA e o Whisper grande
    dubladas: bool                 # baixar as vozes dubladas
    nome: str = ""
    persona: str = "jarvis"
    com_o_pc: bool = True
    atalho: bool = True
    uv: str = field(default_factory=lambda: os.environ.get("NOVA_UV") or shutil.which("uv") or "uv")
    vozes_drive: str = field(default_factory=lambda: os.environ.get("NOVA_VOZES_DRIVE", ""))

    @property
    def app(self) -> Path:
        return self.pasta / "app"

    @property
    def python(self) -> Path:
        return self.app / ".venv" / "bin" / "python"

    @property
    def whisper(self) -> str:
        # Sem placa NVIDIA, o grande no processador demora demais para responder.
        return "large-v3-turbo" if self.nvidia else "small"


# A função de cada passo recebe o contexto e `avisar(fração 0–1 ou -1, texto)`.
Avisar = Callable[[float, str], None]


@dataclass
class Passo:
    id: str
    nome: str
    tamanho: str
    peso: float        # quanto do total ele vale na barra (≈ o tempo)
    fazer: Callable[[Contexto, Avisar], None]


class Cancelado(Exception):
    pass


# -- ajudantes -----------------------------------------------------------------

def _baixar(url: str, destino: Path, avisar: Avisar, texto: str, sha256: str = "") -> None:
    """Baixa continuando do byte onde parou (Range) e confere o sha256."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    if sha256 and destino.is_file() and _sha256(destino) == sha256:
        return
    parcial = destino.with_name(destino.name + ".parcial")
    ja = parcial.stat().st_size if parcial.exists() else 0
    pedido = urllib.request.Request(url, headers={"Range": f"bytes={ja}-"} if ja else {})
    with urllib.request.urlopen(pedido, timeout=60) as r:
        if ja and r.status != 206:      # o servidor não continua: começa de novo
            ja = 0
        total = ja + int(r.headers.get("Content-Length") or 0)
        with open(parcial, "ab" if ja else "wb") as f:
            feito = ja
            while bloco := r.read(1 << 20):
                f.write(bloco)
                feito += len(bloco)
                if total:
                    avisar(feito / total, f"{texto} · {feito / 1e6:.0f} de {total / 1e6:.0f} MB")
    if sha256 and _sha256(parcial) != sha256:
        parcial.unlink()
        raise RuntimeError(f"{destino.name} chegou estragado. Tenta de novo.")
    parcial.replace(destino)


def _sha256(arquivo: Path) -> str:
    soma = hashlib.sha256()
    with open(arquivo, "rb") as f:
        while bloco := f.read(1 << 20):
            soma.update(bloco)
    return soma.hexdigest()


def _rodar(cmd: list[str], avisar: Avisar, texto: str, **kw) -> None:
    """Roda um programa mostrando a última linha dele no texto do passo."""
    avisar(-1, texto)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kw)
    ultimas: list[str] = []
    for linha in p.stdout:  # type: ignore[union-attr]
        linha = linha.strip()
        if linha:
            ultimas = (ultimas + [linha])[-15:]
            avisar(-1, f"{texto} · {linha[:70]}")
    if p.wait() != 0:
        raise RuntimeError(f"{texto} falhou:\n" + "\n".join(ultimas))


def _mudar_config(config: Path, secao: str, chave: str, valor: str) -> None:
    """Troca `chave = ...` dentro de `[secao]` no config.toml (o resto fica igual)."""
    linhas = config.read_text(encoding="utf-8").splitlines(keepends=True)
    dentro = False
    for i, linha in enumerate(linhas):
        if linha.startswith("["):
            dentro = linha.strip() == f"[{secao}]"
        elif dentro and re.match(rf"{re.escape(chave)}\s*=", linha):
            linhas[i] = f"{chave} = {valor}\n"
            break
    else:
        raise KeyError(f"[{secao}] {chave} não está no config.toml")
    config.write_text("".join(linhas), encoding="utf-8")


# -- os passos -------------------------------------------------------------------

def _programa(ctx: Contexto, avisar: Avisar) -> None:
    avisar(-1, "Copiando a NOVA para " + str(ctx.app))
    ctx.app.mkdir(parents=True, exist_ok=True)
    for item in CODIGO.iterdir():
        if item.name in NAO_COPIAR:
            continue
        alvo = ctx.app / item.name
        if item.is_dir():
            shutil.copytree(item, alvo, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(item, alvo)


def _bibliotecas(ctx: Contexto, avisar: Avisar) -> None:
    env = dict(os.environ, VIRTUAL_ENV=str(ctx.app / ".venv"))
    _rodar([ctx.uv, "venv", "--python", "3.12", "--allow-existing", str(ctx.app / ".venv")], avisar,
           "Preparando o Python da NOVA", env=env)
    pacotes = []
    for linha in (ctx.app / "requirements.txt").read_text().splitlines():
        linha = linha.split("#")[0].strip()
        if not linha:
            continue
        # Sem placa NVIDIA: nada de CUDA (o onnxruntime de processador vem com o Whisper).
        if not ctx.nvidia and (linha.startswith("nvidia-") or linha.startswith("onnxruntime-gpu")):
            continue
        pacotes.append(linha)
    _rodar([ctx.uv, "pip", "install", "--python", str(ctx.python), *pacotes], avisar,
           "Baixando as bibliotecas", env=env)
    # O openWakeWord pede o tflite (não existe para o Python 3.12) e a Kokoro puxaria o
    # onnxruntime de processador por cima do de placa: os dois vão sem as dependências.
    _rodar([ctx.uv, "pip", "install", "--python", str(ctx.python), "scipy", "scikit-learn", "requests", "tqdm"],
           avisar, "Baixando as bibliotecas do \"Hey Jarvis\"", env=env)
    _rodar([ctx.uv, "pip", "install", "--python", str(ctx.python), "--no-deps", "openwakeword==0.6.0",
            "kokoro-onnx==0.6.1"], avisar, "Baixando o \"Hey Jarvis\" e a voz leve", env=env)
    if ctx.nvidia:
        # O faster-whisper puxa o onnxruntime de processador, que briga com o de placa.
        _rodar([ctx.uv, "pip", "uninstall", "--python", str(ctx.python), "onnxruntime"], avisar,
               "Trocando o onnxruntime pelo da placa", env=env)
        _rodar([ctx.uv, "pip", "install", "--python", str(ctx.python), "--reinstall", "onnxruntime-gpu==1.22.0"],
               avisar, "Trocando o onnxruntime pelo da placa", env=env)


def _ouvido(ctx: Contexto, avisar: Avisar) -> None:
    destino = ctx.pasta / "modelos" / f"whisper-{ctx.whisper}"
    _rodar([str(ctx.python), "-c",
            "import sys; from faster_whisper import download_model; download_model(sys.argv[1], output_dir=sys.argv[2])",
            ctx.whisper, str(destino)], avisar, f"Baixando o ouvido (Whisper {ctx.whisper})")


def _soltos(prefixo: str) -> Callable[[Contexto, Avisar], None]:
    def fazer(ctx: Contexto, avisar: Avisar) -> None:
        for dentro, (url, sha) in ARQUIVOS_SOLTOS.items():
            if dentro.startswith(prefixo):
                _baixar(url, ctx.app / dentro, avisar, Path(dentro).name, sha)
    return fazer


def _claude(ctx: Contexto, avisar: Avisar) -> None:
    if (Path.home() / ".local/bin/claude").exists():
        return
    _rodar(["bash", "-c", "curl -fsSL https://claude.ai/install.sh | bash"], avisar, "Instalando o Claude Code")


def _dubladas(ctx: Contexto, avisar: Avisar) -> None:
    if not ctx.vozes_drive:
        raise RuntimeError("Este instalador veio sem o endereço das vozes dubladas. Baixa de novo pelo convite.")
    pacote = ctx.pasta / "download" / "nova-vozes-1.zip"
    _baixar(f"https://drive.usercontent.google.com/download?id={ctx.vozes_drive}&export=download&confirm=t",
            pacote, avisar, "Vozes dubladas", VOZES_SHA256)
    avisar(-1, "Abrindo o pacote de vozes")
    with zipfile.ZipFile(pacote) as z:
        z.extractall(ctx.pasta / "vozes")
    pacote.unlink()


def _finalizar(ctx: Contexto, avisar: Avisar) -> None:
    avisar(-1, "Ajustando a NOVA para este PC")
    config = ctx.app / "config.toml"
    _mudar_config(config, "stt", "modelo", json.dumps(str(ctx.pasta / "modelos" / f"whisper-{ctx.whisper}")))
    _mudar_config(config, "stt", "dispositivo", '"cuda"' if ctx.nvidia else '"cpu"')
    # As dubladas tocam pelo servidor do timbre; sem ele, a Kokoro (a reserva) fala.
    _mudar_config(config, "tts", "motor", '"rvc"' if ctx.dubladas else '"kokoro"')
    # Os dados da NOVA (memória, ajustes) ficam em ~/.local/share/jarvis, como no PC do Léo.
    dados = Path.home() / ".local/share/jarvis"
    dados.mkdir(parents=True, exist_ok=True)
    arquivo = dados / "ajustes.json"
    try:
        ajustes = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ajustes = {}
    ajustes["nome"] = ctx.nome
    ajustes["persona_inicial"] = ctx.persona
    if ctx.dubladas:
        ajustes["pasta_vozes"] = str(ctx.pasta / "vozes")
    arquivo.write_text(json.dumps(ajustes, ensure_ascii=False), encoding="utf-8")
    # O menu e o ligar com o PC.
    icone = ctx.app / "jarvis" / "interface" / "icone.png"
    abrir = ctx.app / "jarvis.sh"
    entrada = ("[Desktop Entry]\nType=Application\nName={nome}\nComment={comentario}\nExec={exec}\n"
               f"Icon={icone}\nTerminal=false\nCategories=Utility;\n")
    menu = Path.home() / ".local/share/applications"
    if ctx.atalho:
        menu.mkdir(parents=True, exist_ok=True)
        (menu / "nova.desktop").write_text(entrada.format(
            nome="NOVA", comentario="Liga a NOVA e abre a janela", exec=abrir) + "StartupWMClass=Jarvis\n")
        (menu / "nova-desligar.desktop").write_text(entrada.format(
            nome="Desligar NOVA", comentario="Desliga a NOVA", exec=f"{abrir} --desligar"))
    if ctx.com_o_pc:
        inicio = Path.home() / ".config/autostart"
        inicio.mkdir(parents=True, exist_ok=True)
        (inicio / "nova.desktop").write_text(entrada.format(
            nome="NOVA", comentario="Liga a NOVA ao entrar no PC, escondida perto do relógio",
            exec=f"{abrir} --na-bandeja") + "X-GNOME-Autostart-enabled=true\nX-GNOME-Autostart-Delay=10\n")


def lista(ctx: Contexto) -> list[Passo]:
    passos = [
        Passo("programa", "Programa da NOVA", "40 MB", 1, _programa),
        Passo("bibliotecas", "Bibliotecas", "2,6 GB" if ctx.nvidia else "900 MB", 30 if ctx.nvidia else 12, _bibliotecas),
        Passo("ouvido", "Ouvido (Whisper)", "1,6 GB" if ctx.nvidia else "480 MB", 16 if ctx.nvidia else 6, _ouvido),
        Passo("palavras", "Palavras \"Hey Jarvis\" e \"Hey Friday\"", "4 MB", 1, _soltos("modelos-wakeword/")),
        Passo("voz-leve", "Voz leve (Kokoro)", "350 MB", 4, _soltos("vozes/")),
        Passo("claude", "Claude Code", "220 MB", 3, _claude),
    ]
    if ctx.dubladas:
        passos.append(Passo("dubladas", "Vozes dubladas", "1,5 GB", 15, _dubladas))
    passos.append(Passo("finalizar", "Atalhos e ajustes", "", 1, _finalizar))
    return passos


def feito(ctx: Contexto, passo: Passo) -> bool:
    return (ctx.pasta / ".instalacao" / f"{passo.id}.ok").exists()


def marcar(ctx: Contexto, passo: Passo) -> None:
    (ctx.pasta / ".instalacao").mkdir(parents=True, exist_ok=True)
    (ctx.pasta / ".instalacao" / f"{passo.id}.ok").touch()
