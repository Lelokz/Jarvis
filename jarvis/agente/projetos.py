"""Os projetos do modo code (10/11/2026): onde o Jarvis pode programar com o Léo.

Acha sozinho: tudo em ~/Projetos, os repositórios do SENAI, os jogos do HD que
são projeto (git ou Godot) e a pasta Estudio (as skills de vídeo moram lá).
Fica FORA o projeto da própria NOVA (Regra nº 1, decisão do Léo de 10/11:
"não pode mexer").
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

CASA = Path.home()
HD = Path("/mnt/cab1286d-6765-4c73-9c77-8d3119b4b644")
PROIBIDO = (CASA / "Projetos" / "Jarvis").resolve()
# Onde nascem os projetos novos (decisão do Léo, 10/11/2026: "na pasta de
# projetos do meu HD"; o SSD não guarda projeto).
NOVOS = HD / "Projetos"
MARCAS = (".git", "project.godot", "package.json", "pyproject.toml")


@dataclass(frozen=True)
class Projeto:
    nome: str
    caminho: Path


def _eh_projeto(p: Path) -> bool:
    return any((p / m).exists() for m in MARCAS)


def listar() -> list[Projeto]:
    achados: list[Path] = []
    for pasta in (CASA / "Projetos", NOVOS):
        if pasta.is_dir():
            achados += [p for p in pasta.iterdir() if p.is_dir() and not p.name.startswith(".")]
    for raiz in (CASA / "Estudos" / "SENAI", HD / "Jogos"):
        if raiz.is_dir():
            achados += [p for p in raiz.iterdir() if p.is_dir() and _eh_projeto(p)]
    if (HD / "Estudio").is_dir():
        achados.append(HD / "Estudio")
    vistos, r = set(), []
    for p in achados:
        real = p.resolve()
        if real == PROIBIDO or real in vistos:
            continue
        vistos.add(real)
        r.append(Projeto(p.name, p))
    return sorted(r, key=lambda x: x.nome.lower())


def _palavras(t: str) -> list[str]:
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    t = re.sub(r"([a-z])([A-Z])", r"\1 \2", t)
    return [p for p in re.findall(r"[a-z0-9]+", t) if p not in {"projeto", "o", "a", "do", "da", "de", "no", "na"}]


def eh_o_da_nova(falado: str) -> bool:
    return bool({"jarvis", "nova"} & set(_palavras(falado)))


def achar(falado: str, lista: list[Projeto] | None = None) -> list[Projeto]:
    """Os projetos que batem com o nome falado ("rocket league", "o terror",
    "city empire"). Vazio = nenhum; mais de um = perguntar qual."""
    lista = listar() if lista is None else lista
    pedido = _palavras(falado)
    if not pedido:
        return []
    notas = []
    for p in lista:
        # "CityEmpireUnity" -> city empire unity
        nome = _palavras(re.sub(r"([a-z])([A-Z])", r"\1 \2", p.nome))
        comum = sum(1 for w in pedido if any(n.startswith(w) or w.startswith(n) for n in nome if len(n) > 2 or n == w))
        if comum:
            exato = 1 if nome == pedido else 0
            notas.append((comum, exato, -len(nome), p))
    if not notas:
        return []
    notas.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    melhor = notas[0][:3]
    return [n[3] for n in notas if n[:3] == melhor]


CODIGO = {".py", ".gd", ".js", ".ts", ".tsx", ".jsx", ".kt", ".qml", ".tscn", ".html", ".css", ".cs", ".go", ".rs"}
FORA = {"node_modules", ".git", ".godot", "__pycache__", ".venv", "venv", "build", "dist", ".import", "addons"}


def vocabulario(projeto: Projeto, quantos: int = 30) -> list[str]:
    """Os nomes do projeto que o Whisper precisa ouvir certo: o nome dele e
    os arquivos de código mexidos mais recentemente ("producao", "PainelCanal")."""
    achados: list[tuple[float, str]] = []
    vistos = 0
    for p in projeto.caminho.rglob("*"):
        vistos += 1
        if vistos > 20000:
            break
        if any(parte in FORA for parte in p.parts) or p.suffix.lower() not in CODIGO or not p.is_file():
            continue
        try:
            achados.append((p.stat().st_mtime, p.stem))
        except OSError:
            pass
    nomes = [projeto.nome]
    for _, stem in sorted(achados, reverse=True):
        # Com ponto é gerado ou teste ("loft.spec", "index.audio.worklet"): ninguém fala isso.
        if stem not in nomes and len(stem) > 2 and "." not in stem \
                and stem not in ("__init__", "__main__", "index", "main"):
            nomes.append(stem)
        if len(nomes) >= quantos:
            break
    return nomes


class NomeRuim(ValueError):
    pass


def limpar_nome(nome: str) -> str:
    """Letras, números, espaço, - e _ (o nome vira pasta). "pressure!!" -> "Pressure"."""
    nome = re.sub(r"[^\w \-]", "", nome, flags=re.UNICODE)
    nome = " ".join(nome.split())[:60].strip(" -_")
    return nome[:1].upper() + nome[1:] if nome else ""


def criar(nome: str) -> Projeto:
    """A pasta nova em <HD>/Projetos/<nome>, com git. Não sobrescreve nada."""
    limpo = limpar_nome(nome)
    if not limpo:
        raise NomeRuim("o nome ficou vazio")
    if eh_o_da_nova(limpo):
        raise NomeRuim("esse nome é o da NOVA")
    if any(_palavras(p.nome) == _palavras(limpo) for p in listar()):
        raise NomeRuim(f"já existe um projeto chamado {limpo}")
    if not HD.is_dir():
        raise NomeRuim("o HD não está montado")
    pasta = NOVOS / limpo
    pasta.mkdir(parents=True, exist_ok=False)
    import subprocess
    subprocess.run(["git", "-C", str(pasta), "init", "-q", "-b", "main"], capture_output=True, timeout=20)
    return Projeto(limpo, pasta)


# A seção "Programando" da barra lateral (etapa 3 do tchan, 11/11/2026): os
# projetos que já têm conversa no modo code, do mais novo pro mais velho, com
# quando foi e quantos arquivos estão mudados sem commit ("pra revisar").
SESSOES = Path.home() / ".local/share/jarvis/code-sessoes.json"


def programando(arquivo: Path = SESSOES, limite: int = 6) -> list[dict]:
    import json
    import subprocess
    try:
        sessoes = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    saida = []
    for caminho, sessao in sessoes.items():
        p = Path(caminho)
        if not p.is_dir() or p.resolve() == PROIBIDO:
            continue
        quando = 0.0
        for j in (CASA / ".claude" / "projects").glob(f"*/{sessao}.jsonl"):
            quando = max(quando, j.stat().st_mtime)
        pendentes = 0
        if (p / ".git").exists():
            try:
                r = subprocess.run(["git", "-C", str(p), "status", "--porcelain"], capture_output=True,
                                   text=True, timeout=5)
                pendentes = len([l for l in r.stdout.splitlines() if l.strip()])
            except (OSError, subprocess.SubprocessError):
                pass
        saida.append({"nome": p.name, "caminho": caminho, "quando": quando, "pendentes": pendentes})
    return sorted(saida, key=lambda x: x["quando"], reverse=True)[:limite]
