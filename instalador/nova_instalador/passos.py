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

from nova_instalador.checar import SEM_JANELA, WINDOWS

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
# A parte de tocar do Applio (o timbre do Jarvis): o código no commit testado e os
# dois modelos auxiliares dele (Hugging Face oficial do Applio).
APPLIO = "https://github.com/IAHispano/Applio/archive/da174445ec98d15d006175ac99db3879bd3a73d1.tar.gz"
HF_APPLIO = "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/"
APPLIO_MODELOS = {
    "rvc/models/predictors/rmvpe.pt": (HF_APPLIO + "predictors/rmvpe.pt", "6d62215f4306e3ca278246188607209f09af3dc77ed4232efdd069798c4ec193"),
    "rvc/models/embedders/contentvec/pytorch_model.bin": (HF_APPLIO + "embedders/contentvec/pytorch_model.bin", "d8dd400e054ddf4e6be75dab5a2549db748cc99e756a097c496c099f65a4854e"),
    "rvc/models/embedders/contentvec/config.json": (HF_APPLIO + "embedders/contentvec/config.json", "2ddde063b795d38d9051a7215a092fecf4cfe148b54251e38de51d88d356898b"),
}
# O Go oficial, só para compilar a ponte do WhatsApp (apagado depois).
GO = (("https://go.dev/dl/go1.27.3.windows-amd64.zip", "f26081f438319757f8a1b46d7d0b2c5ec7583d4038e485e0aa725cfde7885fff")
      if WINDOWS else
      ("https://go.dev/dl/go1.27.3.linux-amd64.tar.gz", "65efbc80fdc1fa2cd2631cad5b481777a68e8725f34e89f50fc6ac714e379b40"))
PONTE = Path.home() / ".local/share/jarvis/whatsapp-mcp/whatsapp-bridge"
# Só no Windows: o FFmpeg que a biblioteca de áudio das vozes dubladas procura (no Linux
# ele vem do sistema). A versão fixa do gyan.dev, a que o site do FFmpeg indica.
FFMPEG = ("https://github.com/GyanD/codexffmpeg/releases/download/8.1.2/ffmpeg-8.1.2-full_build-shared.zip",
          "274923c68904a9b76c73b908f57923dafba81155856cd742138515ded570d066")
# Do requirements.txt, o que só existe no Linux (o som e as janelas de lá).
SO_LINUX = ("python-xlib", "pulsectl")
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
        return python_do(self.app / ".venv")

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

def python_do(venv: Path, sem_janela: bool = False) -> Path:
    """O Python de um ambiente (no Windows, o pythonw é o que não abre terminal)."""
    if WINDOWS:
        return venv / "Scripts" / ("pythonw.exe" if sem_janela else "python.exe")
    return venv / "bin" / "python"


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
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                         errors="replace", **SEM_JANELA, **kw)
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


def _env_uv(ctx: Contexto, **mais: str) -> dict:
    """O Python que o uv baixar fica na pasta da NOVA: o ambiente aponta para ele, e o
    cache do instalador (de onde ele viria) pode ser apagado depois."""
    return dict(os.environ, UV_PYTHON_INSTALL_DIR=str(ctx.pasta / "programas" / "python"), **mais)


def _bibliotecas(ctx: Contexto, avisar: Avisar) -> None:
    env = _env_uv(ctx, VIRTUAL_ENV=str(ctx.app / ".venv"))
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
        if WINDOWS and linha.split("=")[0].split(">")[0].strip() in SO_LINUX:
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


CLAUDE = Path.home() / ".local" / "bin" / ("claude.exe" if WINDOWS else "claude")


def _claude(ctx: Contexto, avisar: Avisar) -> None:
    if CLAUDE.exists():
        return
    if WINDOWS:
        _rodar(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                "irm https://claude.ai/install.ps1 | iex"], avisar, "Instalando o Claude Code")
    else:
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


def _programas_vozes(ctx: Contexto, avisar: Avisar) -> None:
    """Um ambiente só para a Friday e o timbre do Jarvis (instalador/requisitos-vozes.txt)."""
    base = ctx.pasta / "programas"
    venv = base / "vozes" / ".venv"
    _rodar([ctx.uv, "venv", "--python", "3.12", "--allow-existing", str(venv)], avisar, "Preparando os programas das vozes",
           env=_env_uv(ctx))
    # O torchcodec vai à parte, só do PyPI: com o índice do PyTorch junto viria a versão
    # de placa, que pede bibliotecas CUDA que não vêm (testado em 28/10/2026).
    lista = base / "requisitos-vozes.txt"
    lista.parent.mkdir(parents=True, exist_ok=True)
    linhas = (CODIGO / "instalador" / "requisitos-vozes.txt").read_text().splitlines()
    # No Windows o torch da placa já traz o CUDA dentro, e o triton e o cuda-* não existem.
    fora = ("torchcodec==",) + (("nvidia-", "cuda-", "triton==") if WINDOWS else ())
    lista.write_text("\n".join(l for l in linhas if not l.startswith(fora)) + "\n")
    codec = next(l for l in linhas if l.startswith("torchcodec=="))
    python = str(python_do(venv))
    _rodar([ctx.uv, "pip", "install", "--python", python,
            "--extra-index-url", "https://download.pytorch.org/whl/cu128", "--index-strategy", "unsafe-best-match",
            "-r", str(lista)], avisar, "Baixando os programas das vozes")
    _rodar([ctx.uv, "pip", "install", "--python", python, "--reinstall-package", "torchcodec", codec],
           avisar, "Baixando os programas das vozes")
    applio = base / "applio"
    if not (applio / "rvc" / "infer" / "infer.py").exists():
        avisar(-1, "Baixando a parte de tocar do Applio")
        import io
        import tarfile
        with urllib.request.urlopen(APPLIO, timeout=120) as r:
            with tarfile.open(fileobj=io.BytesIO(r.read()), mode="r:gz") as tar:
                for membro in tar.getmembers():
                    partes = Path(membro.name).parts
                    if len(partes) > 1 and partes[1] == "rvc":
                        membro.name = str(Path(*partes[1:]))
                        tar.extract(membro, applio, filter="data")
    for dentro, (url, sha) in APPLIO_MODELOS.items():
        _baixar(url, applio / dentro, avisar, Path(dentro).name, sha)
    if WINDOWS and not (base / "ffmpeg" / "bin" / "ffmpeg.exe").exists():
        pacote = base / "download" / "ffmpeg.zip"
        _baixar(FFMPEG[0], pacote, avisar, "FFmpeg (o áudio das vozes)", FFMPEG[1])
        avisar(-1, "Abrindo o FFmpeg")
        with zipfile.ZipFile(pacote) as z:
            z.extractall(base / "download" / "ffmpeg")
        # Dentro do zip vem uma pasta com a versão no nome: vira programas/ffmpeg.
        dentro = next((base / "download" / "ffmpeg").iterdir())
        shutil.rmtree(base / "ffmpeg", ignore_errors=True)
        dentro.replace(base / "ffmpeg")
        shutil.rmtree(base / "download" / "ffmpeg", ignore_errors=True)
        pacote.unlink()


def _ponte(ctx: Contexto, avisar: Avisar) -> None:
    """A ponte do WhatsApp: compila os 3 arquivos de instalador/ponte-whatsapp com o Go
    oficial (SQLite em Go puro: não precisa de gcc). O Go é apagado no fim."""
    base = ctx.pasta / "programas"
    pacote = base / "download" / ("go.zip" if WINDOWS else "go.tar.gz")
    _baixar(GO[0], pacote, avisar, "Go (para montar a ponte do WhatsApp)", GO[1])
    avisar(-1, "Abrindo o Go")
    if WINDOWS:
        with zipfile.ZipFile(pacote) as z:
            z.extractall(base)
    else:
        import tarfile
        with tarfile.open(pacote) as tar:
            tar.extractall(base, filter="data")
    PONTE.mkdir(parents=True, exist_ok=True)
    for nome in ("main.go", "go.mod", "go.sum"):
        shutil.copy2(CODIGO / "instalador" / "ponte-whatsapp" / nome, PONTE / nome)
    cache = base / "go-cache"
    env = dict(os.environ, CGO_ENABLED="0", GOTOOLCHAIN="local", GOPATH=str(cache / "path"),
               GOMODCACHE=str(cache / "mod"), GOCACHE=str(cache / "build"))
    _rodar([str(base / "go" / "bin" / ("go.exe" if WINDOWS else "go")), "build", "-o",
            "whatsapp-bridge.exe" if WINDOWS else "whatsapp-bridge", "."], avisar,
           "Montando a ponte do WhatsApp", cwd=PONTE, env=env)
    # O Go grava o cache dele como somente leitura: libera antes de apagar.
    def liberar(funcao, caminho, _erro) -> None:
        os.chmod(caminho, 0o700)
        os.chmod(os.path.dirname(caminho), 0o700)
        funcao(caminho)
    for sobra in (base / "go", cache):
        if sobra.is_dir():
            shutil.rmtree(sobra, onexc=liberar)
    pacote.unlink(missing_ok=True)


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
        ajustes["programas_vozes"] = str(ctx.pasta / "programas")
    arquivo.write_text(json.dumps(ajustes, ensure_ascii=False), encoding="utf-8")
    if WINDOWS:
        _atalhos_windows(ctx)
        return
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


def _atalho(lnk: Path, ctx: Contexto, argumentos: str, descricao: str) -> None:
    """Um atalho .lnk do Windows (pelo PowerShell, que já vem no Windows). Os valores
    vão pelo ambiente: nome com espaço ou acento não quebra o comando."""
    lnk.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, NOVA_LNK=str(lnk), NOVA_ALVO=str(python_do(ctx.app / ".venv", sem_janela=True)),
               NOVA_ARGS=argumentos, NOVA_PASTA=str(ctx.app), NOVA_DESC=descricao,
               NOVA_ICONE=str(ctx.app / "jarvis" / "interface" / "icone.ico"))
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                    "$a = (New-Object -ComObject WScript.Shell).CreateShortcut($env:NOVA_LNK); "
                    "$a.TargetPath = $env:NOVA_ALVO; $a.Arguments = $env:NOVA_ARGS; "
                    "$a.WorkingDirectory = $env:NOVA_PASTA; $a.Description = $env:NOVA_DESC; "
                    "$a.IconLocation = $env:NOVA_ICONE; $a.Save()"],
                   env=env, check=True, capture_output=True, timeout=30, **SEM_JANELA)


def _atalhos_windows(ctx: Contexto) -> None:
    """Menu Iniciar e a pasta Inicializar (liga com o PC), com o ícone desenhado. Quem
    liga é o jarvis/ligar.py, o irmão do jarvis.sh."""
    # O .ico é o próprio PNG de 256 px dentro do cabeçalho de ícone (o Windows aceita).
    png = (ctx.app / "jarvis" / "interface" / "icone.png").read_bytes()
    cabeca = (b"\0\0\1\0\1\0" + bytes([0, 0, 0, 0]) + (1).to_bytes(2, "little") + (32).to_bytes(2, "little")
              + len(png).to_bytes(4, "little") + (22).to_bytes(4, "little"))
    (ctx.app / "jarvis" / "interface" / "icone.ico").write_bytes(cabeca + png)
    programas = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    if ctx.atalho:
        _atalho(programas / "NOVA.lnk", ctx, "-m jarvis.ligar", "Liga a NOVA e abre a janela")
        _atalho(programas / "Desligar NOVA.lnk", ctx, "-m jarvis.ligar --desligar", "Desliga a NOVA")
    if ctx.com_o_pc:
        _atalho(programas / "Startup" / "NOVA.lnk", ctx, "-m jarvis.ligar --na-bandeja",
                "Liga a NOVA ao entrar no PC, escondida perto do relógio")


def lista(ctx: Contexto) -> list[Passo]:
    passos = [
        Passo("programa", "Programa da NOVA", "40 MB", 1, _programa),
        Passo("bibliotecas", "Bibliotecas", "2,6 GB" if ctx.nvidia else "900 MB", 30 if ctx.nvidia else 12, _bibliotecas),
        Passo("ouvido", "Ouvido (Whisper)", "1,6 GB" if ctx.nvidia else "480 MB", 16 if ctx.nvidia else 6, _ouvido),
        Passo("palavras", "Palavras \"Hey Jarvis\" e \"Hey Friday\"", "4 MB", 1, _soltos("modelos-wakeword/")),
        Passo("voz-leve", "Voz leve (Kokoro)", "350 MB", 4, _soltos("vozes/")),
        Passo("claude", "Claude Code", "220 MB", 3, _claude),
    ]
    passos.append(Passo("ponte", "Ponte do WhatsApp", "75 MB", 4, _ponte))
    if ctx.dubladas:
        passos.append(Passo("dubladas", "Vozes dubladas", "1,5 GB", 15, _dubladas))
        passos.append(Passo("programas-vozes", "Programas das vozes", "~4 GB", 40, _programas_vozes))
    passos.append(Passo("finalizar", "Atalhos e ajustes", "", 1, _finalizar))
    return passos


def feito(ctx: Contexto, passo: Passo) -> bool:
    return (ctx.pasta / ".instalacao" / f"{passo.id}.ok").exists()


def marcar(ctx: Contexto, passo: Passo) -> None:
    (ctx.pasta / ".instalacao").mkdir(parents=True, exist_ok=True)
    (ctx.pasta / ".instalacao" / f"{passo.id}.ok").touch()
