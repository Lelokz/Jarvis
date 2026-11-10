"""Os comentários do canal (Painel do Canal, etapa 4).

A cada sincronização busca os comentários novos de todos os vídeos
(commentThreads com allThreadsRelatedToChannelId, os mais novos primeiro) e
guarda no canal.db. "Lido" é só do PC: o YouTube não sabe disso.
"""

from __future__ import annotations

import datetime as dt
import re
import time

from jarvis.youtube import conta, dados

ESQUEMA = """
CREATE TABLE IF NOT EXISTS comentarios (id TEXT PRIMARY KEY, video TEXT, autor TEXT, foto TEXT, autor_canal TEXT,
  texto TEXT, quando TEXT, likes INTEGER, respostas INTEGER, respondido INTEGER DEFAULT 0, lido INTEGER DEFAULT 0,
  pergunta INTEGER DEFAULT 0, atualizado REAL);
"""
PAGINAS_NA_PRIMEIRA = 10     # 1.000 comentários na primeira vez
PAGINAS_SEMPRE = 2           # as 2 primeiras páginas sempre (respostas e likes mudam)
_PERGUNTA = re.compile(r"\?|^(como|qual|quais|quando|onde|por ?que|pq|quanto|quem|tu vai|vc vai|você vai|cade|cadê)\b",
                       re.IGNORECASE)


def _abrir():
    con = dados.abrir()
    con.executescript(ESQUEMA)
    return con


def eh_pergunta(texto: str) -> bool:
    return bool(_PERGUNTA.search(texto.strip()))


def sincronizar(yt=None) -> int:
    con = _abrir()
    canal = con.execute("SELECT id FROM canal").fetchone()
    if not canal:
        con.close()
        return 0
    meu = canal["id"]
    mais_novo = con.execute("SELECT MAX(quando) FROM comentarios").fetchone()[0] or ""
    primeira = not mais_novo
    yt = yt or conta.youtube()
    novos, token, pagina = 0, None, 0
    while True:
        kw = dict(part="snippet,replies", allThreadsRelatedToChannelId=meu, maxResults=100, order="time",
                  textFormat="plainText")
        if token:
            kw["pageToken"] = token
        r = yt.commentThreads().list(**kw).execute()
        pagina += 1
        velhos = 0
        with con:
            for th in r.get("items", []):
                top = th["snippet"]["topLevelComment"]["snippet"]
                respostas = th.get("replies", {}).get("comments", [])
                respondido = any(c["snippet"].get("authorChannelId", {}).get("value") == meu for c in respostas)
                eh_meu = top.get("authorChannelId", {}).get("value") == meu
                quando = top.get("publishedAt", "")
                if quando <= mais_novo:
                    velhos += 1
                antes = con.execute("SELECT lido, respondido FROM comentarios WHERE id = ?", (th["id"],)).fetchone()
                if not antes:
                    novos += 1
                con.execute("INSERT OR REPLACE INTO comentarios VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    th["id"], th["snippet"].get("videoId", ""), top.get("authorDisplayName", ""),
                    top.get("authorProfileImageUrl", ""), top.get("authorChannelId", {}).get("value", ""),
                    top.get("textOriginal") or top.get("textDisplay", ""), quando, int(top.get("likeCount", 0)),
                    int(th["snippet"].get("totalReplyCount", 0)),
                    1 if (respondido or eh_meu or (antes and antes["respondido"])) else 0,
                    # Comentário meu, ou já lido aqui, continua lido. Na primeira vez, tudo com
                    # mais de 7 dias entra como lido (senão seriam centenas de "novos").
                    1 if (eh_meu or (antes and antes["lido"]) or (primeira and quando < _ha_dias(7))) else 0,
                    1 if eh_pergunta(top.get("textOriginal", "")) else 0, time.time()))
        token = r.get("nextPageToken")
        tudo_velho = velhos == len(r.get("items", []))
        limite = PAGINAS_NA_PRIMEIRA if primeira else 50
        if not token or pagina >= limite or (pagina >= PAGINAS_SEMPRE and tudo_velho):
            break
    con.close()
    return novos


def _ha_dias(n: int) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=n)).isoformat().replace("+00:00", "Z")


def listar(limite: int = 500) -> list[dict]:
    if not dados.BANCO.exists():
        return []
    con = _abrir()
    r = [dict(x) for x in con.execute("SELECT c.*, v.titulo AS video_titulo FROM comentarios c "
                                      "LEFT JOIN videos v ON v.id = c.video ORDER BY quando DESC LIMIT ?", (limite,))]
    con.close()
    return r


def nao_lidos() -> int:
    if not dados.BANCO.exists():
        return 0
    con = _abrir()
    n = con.execute("SELECT COUNT(*) FROM comentarios WHERE lido = 0").fetchone()[0]
    con.close()
    return n


def marcar_lido(ids: list[str] | None = None) -> None:
    """Sem ids: todos."""
    con = _abrir()
    with con:
        if ids is None:
            con.execute("UPDATE comentarios SET lido = 1")
        else:
            con.executemany("UPDATE comentarios SET lido = 1 WHERE id = ?", [(i,) for i in ids])
    con.close()


def responder(comentario: str, texto: str, yt=None) -> None:
    from jarvis.youtube.editar import Recusado
    texto = texto.strip()
    if not texto:
        raise Recusado("a resposta está vazia")
    if len(texto) > 10000:
        raise Recusado("a resposta passou de 10.000 letras")
    yt = yt or conta.youtube()
    yt.comments().insert(part="snippet", body={"snippet": {"parentId": comentario, "textOriginal": texto}}).execute()
    con = _abrir()
    with con:
        con.execute("UPDATE comentarios SET respondido = 1, lido = 1, respostas = respostas + 1 WHERE id = ?",
                    (comentario,))
    con.close()
