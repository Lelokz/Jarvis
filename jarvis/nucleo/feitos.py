"""A galeria "Feitos" e a tela "Agendados" da lateral (etapa 5 do tchan, 11/11/2026).

**Feitos.** Cada arquivo que a NOVA cria (Write), gera por comando (o render
do ffmpeg, o PDF) ou te manda no WhatsApp vira uma linha em
~/.local/share/jarvis/feitos.jsonl, com a conversa de onde veio. A tela mostra
os que ainda existem, com miniatura (a própria imagem; o 1º quadro do vídeo,
feito com o ffmpeg em ~/.cache/jarvis/miniaturas) e o começo do código.
Começou a contar em 11/11/2026: o que ela fez antes não está aqui.

**Agendados.** Os recados (jarvis/nucleo/recados.py) e as rotinas da NOVA
que rodam pelo systemd (painel do canal, faxina, backup).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

ARQUIVO = Path.home() / ".local/share/jarvis/feitos.jsonl"
MINIATURAS = Path.home() / ".cache/jarvis/miniaturas"
CASA = Path.home()

TIPOS = {
    "imagem": {"png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"},
    "video": {"mp4", "webm", "mkv", "mov", "avi", "mp3", "wav", "ogg", "m4a", "flac"},
    "documento": {"pdf", "docx", "doc", "odt", "xlsx", "xls", "ods", "pptx", "odp", "txt", "md", "csv", "html", "epub"},
    "codigo": {"py", "js", "ts", "jsx", "tsx", "kt", "gd", "qml", "c", "h", "cpp", "java", "rs", "sh", "json", "toml",
               "css", "go", "lua", "cs", "rb", "php", "sql", "yaml", "yml", "tscn"},
}
_EXT = {e: t for t, es in TIPOS.items() for e in es}
# O que é da própria NOVA ou passageiro não é "feito".
_FORA = [CASA / ".local/share/jarvis", CASA / ".claude", CASA / ".cache", Path("/tmp"), Path("/proc"), Path("/dev"),
         CASA / "Projetos/Jarvis"]
_ARQ_NO_COMANDO = re.compile(r"""(?:"([^"]+\.(\w{2,5}))"|'([^']+\.(\w{2,5}))'|(\S+\.(\w{2,5})))(?=\s|$|;|&|\|)""")


def tipo_de(caminho: str | Path) -> str | None:
    return _EXT.get(Path(caminho).suffix.lower().lstrip("."))


def _id(caminho: str) -> str:
    return hashlib.sha1(caminho.encode("utf-8")).hexdigest()[:12]


def _vale(caminho: Path) -> bool:
    if tipo_de(caminho) is None:
        return False
    try:
        real = caminho.resolve()
    except OSError:
        return False
    if any(real.is_relative_to(f) for f in _FORA):
        return False
    return real.is_file()


def registrar(caminho: str | Path, sessao: str = "", como: str = "criou", arquivo: Path = ARQUIVO,
              agora: float | None = None) -> bool:
    c = Path(caminho).expanduser()
    if not _vale(c):
        return False
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    with open(arquivo, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": round(agora or time.time(), 1), "caminho": str(c.resolve()), "sessao": sessao,
                            "como": como}, ensure_ascii=False) + "\n")
    return True


def do_comando(comando: str, pasta: Path, desde: float) -> list[Path]:
    """Os arquivos que um comando do terminal acabou de gerar (o ffmpeg que
    renderizou, o pandoc que fez o PDF): os caminhos citados no comando que
    existem e mudaram desde que ele começou."""
    achados = []
    for m in _ARQ_NO_COMANDO.finditer(comando):
        nome = m.group(1) or m.group(3) or m.group(5)
        c = Path(nome).expanduser()
        if not c.is_absolute():
            c = pasta / c
        try:
            if tipo_de(c) and c.is_file() and c.stat().st_mtime >= desde - 2 and c not in achados:
                achados.append(c)
        except OSError:
            continue
    return achados


def _miniatura(caminho: Path, ident: str) -> str:
    """O 1º quadro do vídeo (gerado uma vez). "" = não deu."""
    destino = MINIATURAS / f"{ident}.jpg"
    if destino.is_file():
        return str(destino)
    if not shutil.which("ffmpeg"):
        return ""
    MINIATURAS.mkdir(parents=True, exist_ok=True)
    for inicio in ("1", "0"):
        try:
            subprocess.run(["nice", "-n", "19", "ffmpeg", "-loglevel", "error", "-y", "-ss", inicio, "-i", str(caminho),
                            "-frames:v", "1", "-vf", "scale=480:-2", str(destino)], timeout=12, capture_output=True)
        except (OSError, subprocess.SubprocessError):
            return ""
        if destino.is_file():
            return str(destino)
    return ""


def _duracao(caminho: Path) -> str:
    try:
        r = subprocess.run(["ffmpeg", "-i", str(caminho)], capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.search(r"Duration: (\d+):(\d+):(\d+)", r.stderr)
    if not m:
        return ""
    h, mi, s = map(int, m.groups())
    return f"{h}:{mi:02d}:{s:02d}" if h else f"{mi}:{s:02d}"


def _previa(caminho: Path, linhas: int = 8) -> str:
    try:
        with open(caminho, encoding="utf-8", errors="ignore") as f:
            return "".join(f.readline() for _ in range(linhas)).expandtabs(2)[:600]
    except OSError:
        return ""


def listar(arquivo: Path = ARQUIVO, limite: int = 120, novas_miniaturas: int = 8) -> list[dict]:
    """Os feitos que ainda existem, do mais novo pro mais velho (sem repetir)."""
    try:
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    vistos, saida = set(), []
    for l in reversed(linhas):
        try:
            e = json.loads(l)
        except ValueError:
            continue
        c = e.get("caminho") or ""
        if c in vistos:
            continue
        vistos.add(c)
        p = Path(c)
        if not p.is_file():
            continue
        ident, tipo = _id(c), tipo_de(p)
        item = {"id": ident, "caminho": c, "nome": p.name, "pasta": str(p.parent), "tipo": tipo,
                "quando": e.get("t", 0), "sessao": e.get("sessao", ""), "como": e.get("como", "criou"),
                "miniatura": "", "previa": "", "duracao": ""}
        if tipo == "imagem" and p.suffix.lower() != ".svg":
            item["miniatura"] = c
        elif tipo == "video" and p.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov", ".avi"):
            existe = (MINIATURAS / f"{ident}.jpg").is_file()
            if existe or novas_miniaturas > 0:
                item["miniatura"] = _miniatura(p, ident)
                novas_miniaturas -= 0 if existe else 1
            item["duracao"] = _duracao(p) if len(saida) < 40 else ""
        elif tipo == "codigo":
            item["previa"] = _previa(p)
        saida.append(item)
        if len(saida) >= limite:
            break
    return saida


def caminho_de(ident: str, arquivo: Path = ARQUIVO, miniatura: bool = False) -> Path | None:
    """Pra porta remota: só o que está na galeria (nunca um caminho qualquer)."""
    if not re.fullmatch(r"[0-9a-f]{12}", ident or ""):
        return None
    try:
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for l in reversed(linhas):
        try:
            c = json.loads(l).get("caminho") or ""
        except ValueError:
            continue
        if _id(c) == ident:
            p = Path(c)
            if miniatura and tipo_de(p) == "video":
                m = MINIATURAS / f"{ident}.jpg"
                return m if m.is_file() else None
            return p if p.is_file() else None
    return None


# -- Agendados: as rotinas da NOVA (systemd) ------------------------------------

ROTINAS = [
    ("jarvis-canal.timer", "Painel do canal", "confere comentários com pergunta e os marcos do canal", "a cada 30 min", "yt"),
    ("jarvis-faxina.timer", "Faxina do SSD", "apaga cache e temporários velhos (nunca arquivo teu)", "toda segunda, 00:20", "vassoura"),
    ("jarvis-backup.timer", "Backup mensal pro Drive", "a NOVA inteira, com senha", "dia 1 de cada mês", "nuvem"),
]


def rotinas() -> list[dict]:
    proximas = {}
    try:
        r = subprocess.run(["systemctl", "--user", "list-timers", "--all", "--output=json"],
                           capture_output=True, text=True, timeout=8)
        for t in json.loads(r.stdout or "[]"):
            if t.get("next"):
                proximas[t.get("unit")] = t["next"] / 1_000_000
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    saida = []
    for unidade, nome, descricao, quando, icone in ROTINAS:
        if unidade not in proximas and not (Path.home() / ".config/systemd/user" / unidade).exists():
            continue
        estado = "ligado" if unidade in proximas else "desligado"
        if unidade == "jarvis-backup.timer" and not shutil.which("rclone"):
            estado = "falta configurar"
        saida.append({"nome": nome, "descricao": descricao, "quando": quando, "icone": icone,
                      "proxima": proximas.get(unidade, 0), "estado": estado})
    return saida
