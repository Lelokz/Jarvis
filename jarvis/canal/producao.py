"""A Produção do Painel do Canal (etapa 3): o quadro de etapas de cada vídeo,
da ideia até postado. Fica só no PC (o YouTube não sabe dessas coisas), no
mesmo canal.db.

Quando o vídeo aparece no canal (agendado ou publicado), o card dele vai
sozinho para "Agendado"/"Postado", achado pelo título.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata

from jarvis.canal import dados

COLUNAS = ("ideia", "gravando", "editando", "pronto", "agendado", "postado")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS cards (id INTEGER PRIMARY KEY, titulo TEXT NOT NULL, jogo TEXT DEFAULT '',
  coluna TEXT NOT NULL DEFAULT 'ideia', data TEXT DEFAULT '', notas TEXT DEFAULT '', arquivos TEXT DEFAULT '[]',
  video TEXT DEFAULT '', ordem REAL DEFAULT 0, criado REAL, atualizado REAL);
"""
CAMPOS = ("titulo", "jogo", "coluna", "data", "notas", "arquivos", "video", "ordem")


def _abrir():
    con = dados.abrir()
    con.executescript(ESQUEMA)
    return con


def _linha(r) -> dict:
    d = dict(r)
    d["arquivos"] = json.loads(d["arquivos"] or "[]")
    return d


def listar() -> list[dict]:
    if not dados.BANCO.exists():
        return []
    con = _abrir()
    r = [_linha(x) for x in con.execute("SELECT * FROM cards ORDER BY coluna, ordem, id")]
    con.close()
    return r


def _limpar(campos: dict) -> dict:
    c = {k: v for k, v in campos.items() if k in CAMPOS}
    if "titulo" in c:
        c["titulo"] = " ".join(str(c["titulo"]).split())
        if not c["titulo"]:
            raise ValueError("o card precisa de um título")
    if "coluna" in c and c["coluna"] not in COLUNAS:
        raise ValueError(f"coluna desconhecida: {c['coluna']}")
    if c.get("data") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", c["data"]):
        raise ValueError("data no formato errado")
    if "arquivos" in c:
        c["arquivos"] = json.dumps(list(dict.fromkeys(c["arquivos"])), ensure_ascii=False)
    return c


def criar(campos: dict) -> int:
    c = _limpar({"coluna": "ideia", **campos})
    if "titulo" not in c:
        raise ValueError("o card precisa de um título")
    con = _abrir()
    with con:
        fim = con.execute("SELECT COALESCE(MAX(ordem), 0) + 1 FROM cards WHERE coluna = ?", (c["coluna"],)).fetchone()[0]
        c.setdefault("ordem", fim)
        c["criado"] = c["atualizado"] = time.time()
        cur = con.execute(f"INSERT INTO cards ({','.join(c)}) VALUES ({','.join('?' * len(c))})", list(c.values()))
    con.close()
    return cur.lastrowid


def atualizar(card: int, campos: dict) -> None:
    c = _limpar(campos)
    if not c:
        return
    c["atualizado"] = time.time()
    con = _abrir()
    with con:
        con.execute(f"UPDATE cards SET {', '.join(k + ' = ?' for k in c)} WHERE id = ?", [*c.values(), card])
    con.close()


def mover(card: int, coluna: str) -> None:
    con = _abrir()
    fim = con.execute("SELECT COALESCE(MAX(ordem), 0) + 1 FROM cards WHERE coluna = ?", (coluna,)).fetchone()[0]
    con.close()
    atualizar(card, {"coluna": coluna, "ordem": fim})


def apagar(card: int) -> None:
    con = _abrir()
    with con:
        con.execute("DELETE FROM cards WHERE id = ?", (card,))
    con.close()


def _palavras(t: str) -> set[str]:
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return {p for p in re.findall(r"\w+", t) if len(p) > 1}


def parecidos(a: str, b: str) -> bool:
    """O título do card e o do vídeo falam do mesmo vídeo? (o título final
    costuma mudar um pouco: "Doors hotel" -> "DOORS: zerei o HOTEL+")."""
    pa, pb = _palavras(a), _palavras(b)
    if not pa or not pb:
        return False
    comum = len(pa & pb)
    return comum / len(pa | pb) >= 0.6 or (comum >= 2 and comum / min(len(pa), len(pb)) >= 0.8)


def ligar_postados() -> int:
    """Card de vídeo que já está no canal: vai pra Agendado/Postado sozinho."""
    if not dados.BANCO.exists():
        return 0
    con = _abrir()
    videos = [dict(v) for v in con.execute("SELECT id, titulo, visibilidade, agendado FROM videos")]
    usados = {r[0] for r in con.execute("SELECT video FROM cards WHERE video != ''")}
    mudou = 0
    for card in con.execute("SELECT * FROM cards WHERE coluna != 'postado'").fetchall():
        v = next((v for v in videos if v["id"] == card["video"]), None) if card["video"] else \
            next((v for v in videos if v["id"] not in usados and parecidos(card["titulo"], v["titulo"])), None)
        if not v:
            continue
        coluna = "agendado" if v["agendado"] else "postado" if v["visibilidade"] == "public" else card["coluna"]
        if coluna != card["coluna"] or card["video"] != v["id"]:
            with con:
                con.execute("UPDATE cards SET coluna = ?, video = ?, atualizado = ? WHERE id = ?",
                            (coluna, v["id"], time.time(), card["id"]))
            usados.add(v["id"])
            mudou += 1
    con.close()
    return mudou
