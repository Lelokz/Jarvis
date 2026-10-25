"""As memórias do Jarvis, para a aba "Memórias" da janela e do app (25/10/2026).

Cada memória é um arquivo de texto (markdown) que o próprio Jarvis cria e
edita com as ferramentas de arquivo de sempre; aqui só se lista, lê e salva
o que o Léo editar à mão. Nenhuma ferramenta especial: memória nova (um
grupo, uma pessoa) é só um arquivo novo na pasta, e aparece na lista sozinha.

- `jarvis`: o que o Jarvis e a Friday sabem do Léo (a casa, CLAUDE.md, que o
  Claude Code lê sozinho);
- `recados`: os recados que o Jarvis do PC deixou para si mesmo;
- `grupo:<id>`: a memória de um grupo de WhatsApp (memorias/grupos/<id>/
  memoria.md), escrita pelo Jarvis daquele grupo (anotações, lista, recados);
- `pessoa:<nome>`: o que o Jarvis anotou sobre uma pessoa (memorias/pessoas/).

Salvar compara a versão que a tela abriu com a do disco: se o Jarvis mudou
o arquivo enquanto o Léo editava, não sobrescreve (volta `conflito` com o
texto atual). Python puro, portável (Windows).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
from pathlib import Path

BASE = Path.home() / ".local/share/jarvis"
CASA = BASE / "casa"
PASTA = BASE / "memorias"
GRUPOS = PASTA / "grupos"
PESSOAS = PASTA / "pessoas"
_ID = re.compile(r"[\w.-]{1,80}")
MAX_TEXTO = 200_000


def pasta_do_grupo(jid: str) -> Path:
    """A pasta de um grupo pelo jid ("1203...@g.us" -> grupos/1203...)."""
    return GRUPOS / re.sub(r"[^\w.-]", "_", jid.split("@")[0])


def _caminho(ident: str) -> Path | None:
    if ident == "jarvis":
        return CASA / "CLAUDE.md"
    if ident == "recados":
        return CASA / "recados.md"
    tipo, _, nome = ident.partition(":")
    if not _ID.fullmatch(nome) or nome in (".", ".."):
        return None
    if tipo == "grupo":
        return GRUPOS / nome / "memoria.md"
    if tipo == "pessoa":
        return PESSOAS / f"{nome}.md"
    return None


def _titulo(arquivo: Path, padrao: str) -> str:
    """O primeiro título (# ...) do arquivo, ou o nome padrão."""
    try:
        with arquivo.open(encoding="utf-8") as f:
            for linha in f:
                if linha.startswith("# "):
                    return linha[2:].strip()[:80] or padrao
    except OSError:
        pass
    return padrao


def _versao(texto: str) -> str:
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


def _item(ident: str, arquivo: Path, tipo: str, padrao: str) -> dict:
    quando = dt.datetime.fromtimestamp(arquivo.stat().st_mtime).isoformat(timespec="minutes")
    return {"id": ident, "titulo": _titulo(arquivo, padrao), "tipo": tipo, "atualizado": quando}


def listar() -> list[dict]:
    """Todas as memórias: a do Jarvis primeiro, depois grupos e pessoas."""
    saida = []
    if (CASA / "CLAUDE.md").exists():
        saida.append(_item("jarvis", CASA / "CLAUDE.md", "personas", "Jarvis e Friday") | {"titulo": "Jarvis e Friday"})
    if (CASA / "recados.md").exists():
        saida.append(_item("recados", CASA / "recados.md", "recados", "Recados do Jarvis") | {"titulo": "Recados do Jarvis"})
    if GRUPOS.is_dir():
        for arq in sorted(GRUPOS.glob("*/memoria.md")):
            saida.append(_item(f"grupo:{arq.parent.name}", arq, "grupo", f"Grupo {arq.parent.name}"))
    if PESSOAS.is_dir():
        for arq in sorted(PESSOAS.glob("*.md")):
            saida.append(_item(f"pessoa:{arq.stem}", arq, "pessoa", arq.stem.replace("-", " ").title()))
    return saida


def ler(ident: str) -> dict:
    arquivo = _caminho(ident)
    if arquivo is None:
        raise ValueError("memória desconhecida")
    texto = arquivo.read_text(encoding="utf-8") if arquivo.exists() else ""
    titulo = next((m["titulo"] for m in listar() if m["id"] == ident), ident)
    return {"id": ident, "titulo": titulo, "texto": texto, "versao": _versao(texto)}


def salvar(ident: str, texto: str, versao: str) -> dict:
    """Grava o que o Léo editou, se ninguém mudou o arquivo desde que ele
    abriu (`versao`). Senão volta {"ok": False, "conflito": True, ...} com o
    texto atual, para a tela mostrar e ele decidir."""
    arquivo = _caminho(ident)
    if arquivo is None:
        raise ValueError("memória desconhecida")
    if len(texto) > MAX_TEXTO:
        raise ValueError("texto grande demais")
    atual = arquivo.read_text(encoding="utf-8") if arquivo.exists() else ""
    if versao != _versao(atual):
        return {"id": ident, "ok": False, "conflito": True, "texto": atual, "versao": _versao(atual)}
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_name(arquivo.name + ".salvando")
    temporario.write_text(texto, encoding="utf-8")
    os.replace(temporario, arquivo)
    return {"id": ident, "ok": True, "conflito": False, "texto": texto, "versao": _versao(texto)}
