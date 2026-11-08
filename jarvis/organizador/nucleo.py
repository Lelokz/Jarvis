"""O organizador por dentro: o que vigiar, perguntar ao Claude, mover e anotar."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CASA = Path.home()
HD = Path("/mnt/cab1286d-6765-4c73-9c77-8d3119b4b644")
DADOS = CASA / ".local/share/jarvis"
MAPA = DADOS / "casa" / "organizador-mapa.md"
DIARIO = DADOS / "organizador-diario.jsonl"
PENDENTES = DADOS / "organizador-pendentes.json"
TRABALHO = HD / "Arquivo" / "tmp-organizador"   # quadros de vídeo, páginas de PDF (no HD, não no SSD)

GRAVACOES = HD / "Estudio" / "Gravacoes"
EDICAO = HD / "Estudio" / "Edicao"
# Onde chega coisa nova. As gravações: só os vídeos soltos na raiz (os que já
# estão em subpastas já foram organizados).
VIGIADAS = [CASA / "Downloads", GRAVACOES]   # o Flameshot salva direto em Downloads (08/11)
NAO_SAO_ITEM: set = set()
VIDEO = (".mov", ".mkv", ".mp4", ".flv", ".webm")

RAIZES = [CASA / "Imagens", CASA / "Documentos", CASA / "Estudos", CASA / "Vídeos", CASA / "Músicas",
          HD / "Jogos", HD / "Midia", GRAVACOES]
PROIBIDAS = [HD / "Jogos" / "Projeto Terror", HD / "Jogos" / "Projeto Rocket League", EDICAO,
             CASA / "Downloads"]

IGNORAR_FINAIS = (".crdownload", ".part", ".partial", ".tmp", ".download", ".opdownload")
ESPERA_S = 60            # parado há tanto tempo = terminou de baixar
ESPERA_GRAVACAO_S = 180  # o OBS às vezes para de escrever um pouco no fim
TENTAR_DE_NOVO_S = 600
PAUSA_NO_LIMITE_S = 1800   # bateu o limite da assinatura: para tudo por meia hora

CLAUDE = str(CASA / ".local/bin/claude")
FFMPEG = str(CASA / ".local/share/lelokz-estudio/ffmpeg")
FERRAMENTAS = [
    "Read", "Glob", "Grep",
    "Bash(file:*)", "Bash(ls:*)", "Bash(du:*)", "Bash(head:*)",
    "Bash(unzip -l:*)", "Bash(unzip -p:*)", "Bash(7z l:*)",
    "Bash(tar -tf:*)", "Bash(tar -tzf:*)",
    "Bash(pdftotext:*)", "Bash(pdfinfo:*)", "Bash(pdftoppm:*)",
    "Bash(ffprobe:*)", "Bash(ffmpeg:*)",
]
ESQUEMA = {
    "type": "object",
    "properties": {
        "relatorio": {"type": "string"},
        "certeza": {"type": "boolean"},
        "pergunta": {"type": "string"},
        "pasta_destino": {"type": "string"},
        "nome": {"type": "string"},
        "regra": {"type": "string"},
    },
    "required": ["relatorio", "certeza", "pasta_destino", "nome"],
}


# ---------- o que é item novo ----------

def ignorar(p: Path) -> bool:
    nome = p.name
    if nome.startswith(".") or nome.lower().endswith(IGNORAR_FINAIS) or nome.startswith("Não confirmado"):
        return True
    if p in NAO_SAO_ITEM:
        return True
    if p.parent == GRAVACOES and not (p.is_file() and p.suffix.lower() in VIDEO):
        return True
    return False


def itens_novos():
    pendentes = set(ler_pendentes())
    for pasta in VIGIADAS:
        if pasta.is_dir():
            for p in pasta.iterdir():
                if not ignorar(p) and str(p) not in pendentes:
                    yield p


def assinatura(p: Path):
    """Tamanho total e última modificação. Se mudou, ainda está chegando."""
    try:
        if p.is_file():
            st = p.stat()
            return (st.st_size, st.st_mtime)
        total, ultima = 0, p.stat().st_mtime
        for raiz, _, arquivos in os.walk(p):
            for a in arquivos:
                st = os.stat(os.path.join(raiz, a))
                total += st.st_size
                ultima = max(ultima, st.st_mtime)
        return (total, ultima)
    except OSError:
        return None


def aberto(p: Path) -> bool:
    """Algum programa está com o arquivo aberto (o OBS gravando, o navegador baixando)?"""
    alvo = str(p)
    for fd in Path("/proc").glob("[0-9]*/fd/*"):
        try:
            if os.readlink(fd) == alvo:
                return True
        except OSError:
            continue
    return False


def em_edicao(p: Path) -> bool:
    """Uma gravação que um projeto de edição usa não sai do lugar (quebraria a edição)."""
    if p.parent != GRAVACOES or not EDICAO.is_dir():
        return False
    r = subprocess.run(["grep", "-rlF", "--include=*.json", "--include=*.md", "--include=*.tsx",
                        "--include=*.ts", "--include=*.py", "--include=*.sh", "-m1", p.name, str(EDICAO)],
                       capture_output=True, text=True, timeout=120)
    return bool(r.stdout.strip())


# ---------- o pedido ao Claude ----------

def arvore(limite=500) -> str:
    linhas = []
    for raiz in RAIZES:
        linhas.append(str(raiz))
        for atual, pastas, _ in os.walk(raiz):
            pastas[:] = sorted(d for d in pastas if not d.startswith("."))
            nivel = len(Path(atual).relative_to(raiz).parts)
            if nivel >= 3:
                pastas[:] = []
            for d in pastas:
                linhas.append("  " * (nivel + 1) + d + "/")
                if len(linhas) > limite:
                    return "\n".join(linhas) + "\n  ..."
    return "\n".join(linhas)


def ultimas_decisoes(n=30) -> str:
    saida = [f"- {Path(d['origem']).name} -> {d['destino']}" for d in movidos()[-n:]]
    return "\n".join(saida) or "(nenhuma ainda)"


def perguntar_ao_claude(item: Path, trabalho: Path) -> dict:
    tipo = subprocess.run(["file", "-b", str(item)], capture_output=True, text=True).stdout.strip()
    mapa = MAPA.read_text(encoding="utf-8") if MAPA.exists() else "(vazio)"
    pedido = f"""{(AQUI / 'regras.md').read_text(encoding='utf-8')}

---

{mapa}

---

Item novo: {item}
Tipo (comando file): {tipo}
Tamanho: {assinatura(item)[0] / 1_000_000:.1f} MB
Pasta de trabalho (quadros de vídeo, páginas de PDF): {trabalho}

Pastas que já existem:
{arvore()}

Últimas decisões (pra manter o padrão):
{ultimas_decisoes()}

Analise e responda com relatorio, certeza, pergunta (só sem certeza), pasta_destino
(caminho absoluto), nome e regra (só se a pasta for nova)."""
    env = dict(os.environ, PATH=f"{FFMPEG}:{os.environ.get('PATH', '')}")
    # Sonnet, esforço médio: a primeira arrumação com Opus no alto (08/11/2026)
    # gastou o limite de 5 h inteiro em ~75 arquivos, e o Jarvis usa a mesma conta.
    cmd = [CLAUDE, "-p", pedido, "--model", "claude-sonnet-5-5", "--effort", "medium",
           "--no-session-persistence", "--output-format", "json",
           "--json-schema", json.dumps(ESQUEMA),
           "--allowedTools", *FERRAMENTAS,
           "--disallowedTools", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch",
           "--add-dir", str(item.parent), str(trabalho)]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=trabalho, env=env, timeout=900)
    d = json.loads(r.stdout)
    if d.get("is_error") or "structured_output" not in d:
        raise RuntimeError(d.get("result") or r.stderr[-500:])
    return d["structured_output"]


# ---------- mover e anotar ----------

def destino_valido(pasta: Path) -> bool:
    pasta = Path(os.path.normpath(pasta))
    if any(p == pasta or p in pasta.parents for p in PROIBIDAS):
        return False
    cyber = HD / "Jogos" / "Mods Cyberpunk 2077"
    if cyber in pasta.parents:
        categoria = pasta.relative_to(cyber).parts[0]
        if categoria.startswith(("_", "07", "08", "Duplicados")):
            return False
    return any(r == pasta or r in pasta.parents for r in RAIZES)


def nome_livre(pasta: Path, nome: str, ext: str) -> Path:
    nome = nome.replace("/", "-").strip() or "Sem nome"
    alvo = pasta / f"{nome}{ext}"
    n = 2
    while alvo.exists():
        alvo = pasta / f"{nome} ({n}){ext}"
        n += 1
    return alvo


def anotar(**dados) -> None:
    dados["quando"] = datetime.now().isoformat(timespec="seconds")
    DIARIO.parent.mkdir(parents=True, exist_ok=True)
    with DIARIO.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dados, ensure_ascii=False) + "\n")


def mover(item: Path, pasta: Path, nome: str, relatorio: str = "", regra: str = "") -> dict:
    """Move de verdade (validado), anota e devolve {destino, pasta_nova}."""
    pasta = Path(os.path.normpath(pasta))
    if not destino_valido(pasta):
        raise RuntimeError(f"destino fora das pastas permitidas: {pasta}")
    ext = item.suffix if item.is_file() else ""
    if ext and nome.lower().endswith(ext.lower()):
        nome = nome[: -len(ext)]
    alvo = nome_livre(pasta, nome, ext)
    pasta_nova = not pasta.exists()
    pasta.mkdir(parents=True, exist_ok=True)
    shutil.move(str(item), str(alvo))
    anotar(acao="moveu", origem=str(item), destino=str(alvo), pasta_nova=pasta_nova, relatorio=relatorio)
    if pasta_nova and regra:
        with MAPA.open("a", encoding="utf-8") as f:
            f.write(f"- {regra.strip()}\n")
    tirar_pendente(item)
    return {"destino": str(alvo), "pasta_nova": pasta_nova, "pasta": str(pasta)}


def organizar(item: Path) -> dict:
    """Analisa e move. Devolve {"movido": {...}, "relatorio"} ou {"pergunta", "relatorio"}."""
    trabalho = TRABALHO / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    trabalho.mkdir(parents=True, exist_ok=True)
    try:
        d = perguntar_ao_claude(item, trabalho)
    finally:
        shutil.rmtree(trabalho, ignore_errors=True)
    if not d.get("certeza", True) and d.get("pergunta"):
        guardar_pendente(item, d["pergunta"], d["relatorio"])
        anotar(acao="perguntou", origem=str(item), pergunta=d["pergunta"], relatorio=d["relatorio"])
        return {"pergunta": d["pergunta"], "relatorio": d["relatorio"]}
    m = mover(item, Path(d["pasta_destino"]), d["nome"], d["relatorio"], d.get("regra", ""))
    return {"movido": m, "relatorio": d["relatorio"]}


# ---------- pendentes (esperando o Léo responder) ----------

def ler_pendentes() -> dict:
    try:
        return json.loads(PENDENTES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def guardar_pendente(item: Path, pergunta: str, relatorio: str) -> None:
    p = ler_pendentes()
    p[str(item)] = {"pergunta": pergunta, "relatorio": relatorio,
                    "quando": datetime.now().isoformat(timespec="minutes")}
    PENDENTES.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")


def tirar_pendente(item: Path) -> None:
    p = ler_pendentes()
    if p.pop(str(item), None) is not None:
        PENDENTES.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------- o diário e o desfazer ----------

def movidos() -> list[dict]:
    if not DIARIO.exists():
        return []
    linhas = [json.loads(l) for l in DIARIO.read_text(encoding="utf-8").splitlines() if l.strip()]
    desfeitos = {d["destino"] for d in linhas if d["acao"] == "desfez"}
    return [d for d in linhas if d["acao"] == "moveu" and d["destino"] not in desfeitos]


def devolver(d: dict) -> str:
    destino, origem = Path(d["destino"]), Path(d["origem"])
    if not destino.exists():
        return f"não achei mais: {destino}"
    alvo, n = origem, 2
    while alvo.exists():
        alvo = origem.with_name(f"{origem.stem} ({n}){origem.suffix}")
        n += 1
    alvo.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(destino), str(alvo))
    anotar(acao="desfez", destino=d["destino"], voltou_para=str(alvo))
    return f"voltou: {alvo}"


# ---------- a vigia (thread do assistente) ----------

class Vigia:
    """Olha as pastas e organiza o que parou de mudar. `avisar(tipo, dados)` é
    chamado com "movido" ou "pergunta" (o assistente decide como contar)."""

    def __init__(self, avisar) -> None:
        self.avisar = avisar
        self._vistos: dict[Path, tuple] = {}
        self._falhou: dict[Path, float] = {}
        self._parados: set[Path] = set()   # gravação em edição: nunca mais olha
        self._pausa_ate = 0.0                # limite da assinatura: espera em vez de insistir

    def uma_volta(self) -> None:
        agora = time.time()
        if agora < self._pausa_ate:
            return
        atuais = set(itens_novos()) - self._parados
        for p in list(self._vistos):
            if p not in atuais:
                del self._vistos[p]
        for item in sorted(atuais):
            sig = assinatura(item)
            if sig is None:
                continue
            if self._vistos.get(item, (None,))[0] != sig:
                self._vistos[item] = (sig, agora)
                continue
            espera = ESPERA_GRAVACAO_S if item.parent == GRAVACOES else ESPERA_S
            if agora - self._vistos[item][1] < espera or agora - self._falhou.get(item, 0) < TENTAR_DE_NOVO_S:
                continue
            if aberto(item):
                continue
            if em_edicao(item):
                self._parados.add(item)
                continue
            try:
                r = organizar(item)
                self._vistos.pop(item, None)
                self.avisar("pergunta" if "pergunta" in r else "movido", {"item": str(item), **r})
            except Exception as e:
                self._falhou[item] = agora
                anotar(acao="falhou", origem=str(item), erro=str(e)[:500])
                if "limit" in str(e).lower():
                    self._pausa_ate = agora + PAUSA_NO_LIMITE_S
                    return
