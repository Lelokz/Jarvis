"""Os dados do canal guardados no PC (Painel do Canal, 09/11/2026).

A cada 30 minutos (timer jarvis-canal) o PC pergunta ao YouTube e guarda tudo
em ~/.local/share/jarvis/canal/canal.db. A janela, o app do celular e o Jarvis
leem daqui: abre na hora, e com a internet caída ainda mostra o último que tinha.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import statistics
import time
import unicodedata

from jarvis.youtube import conta

BANCO = conta.PASTA / "canal.db"
DIAS_DE_HISTORICO = 365
VIDEOS_COM_DIAS = 15        # os últimos N vídeos ganham as views dia a dia (para comparar)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS canal (id TEXT PRIMARY KEY, titulo TEXT, inscritos INTEGER, views INTEGER,
  videos INTEGER, uploads TEXT, foto TEXT, atualizado REAL);
CREATE TABLE IF NOT EXISTS videos (id TEXT PRIMARY KEY, titulo TEXT, descricao TEXT, publicado TEXT,
  duracao_s INTEGER, views INTEGER, likes INTEGER, comentarios INTEGER, visibilidade TEXT,
  agendado TEXT, thumb TEXT, tags TEXT, atualizado REAL);
CREATE TABLE IF NOT EXISTS dias (dia TEXT PRIMARY KEY, views INTEGER, minutos INTEGER,
  ganhos INTEGER, perdidos INTEGER, likes INTEGER);
CREATE TABLE IF NOT EXISTS video_dias (video TEXT, dia TEXT, views INTEGER, PRIMARY KEY (video, dia));
"""


def abrir() -> sqlite3.Connection:
    conta.PASTA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(BANCO, timeout=10)
    con.executescript(ESQUEMA)
    con.row_factory = sqlite3.Row
    return con


def _segundos(iso: str) -> int:
    """PT1H2M3S -> 3723."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def _paginas(pedido_de, **kw):
    token = None
    while True:
        r = pedido_de(pageToken=token, **kw).execute() if token else pedido_de(**kw).execute()
        yield r
        token = r.get("nextPageToken")
        if not token:
            return


# -- sincronizar ------------------------------------------------------------------------

def sincronizar(yt=None, an=None, hoje: dt.date | None = None) -> dict:
    yt = yt or conta.youtube()
    an = an or conta.analytics()
    hoje = hoje or dt.date.today()
    agora = time.time()
    c = yt.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()["items"][0]
    uploads = c["contentDetails"]["relatedPlaylists"]["uploads"]
    con = abrir()
    primeira = con.execute("SELECT COUNT(*) FROM canal").fetchone()[0] == 0
    with con:
        con.execute("INSERT OR REPLACE INTO canal VALUES (?,?,?,?,?,?,?,?)", (
            c["id"], c["snippet"]["title"], int(c["statistics"].get("subscriberCount", 0)),
            int(c["statistics"].get("viewCount", 0)), int(c["statistics"].get("videoCount", 0)), uploads,
            c["snippet"].get("thumbnails", {}).get("high", {}).get("url", ""), agora))

    ids = [i["contentDetails"]["videoId"]
           for p in _paginas(yt.playlistItems().list, part="contentDetails", playlistId=uploads, maxResults=50)
           for i in p.get("items", [])]
    for k in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,statistics,status,contentDetails", id=",".join(ids[k:k + 50]),
                             maxResults=50).execute()
        with con:
            for v in r.get("items", []):
                sn, st, ss = v["snippet"], v.get("statistics", {}), v.get("status", {})
                thumbs = sn.get("thumbnails", {})
                thumb = (thumbs.get("maxres") or thumbs.get("high") or thumbs.get("medium") or {}).get("url", "")
                con.execute("INSERT OR REPLACE INTO videos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    v["id"], sn.get("title", ""), sn.get("description", ""), sn.get("publishedAt", ""),
                    _segundos(v.get("contentDetails", {}).get("duration", "")),
                    int(st.get("viewCount", 0)), int(st.get("likeCount", 0)), int(st.get("commentCount", 0)),
                    ss.get("privacyStatus", ""), ss.get("publishAt", ""), thumb,
                    json.dumps(sn.get("tags", []), ensure_ascii=False), agora))
        # Vídeo apagado no YouTube sai daqui também.
    if ids:
        with con:
            con.execute(f"DELETE FROM videos WHERE id NOT IN ({','.join('?' * len(ids))})", ids)

    inicio = (hoje - dt.timedelta(days=DIAS_DE_HISTORICO)).isoformat()
    r = an.reports().query(ids="channel==MINE", startDate=inicio, endDate=hoje.isoformat(),
                           metrics="views,estimatedMinutesWatched,subscribersGained,subscribersLost,likes",
                           dimensions="day", sort="day").execute()
    with con:
        for dia, views, minutos, ganhos, perdidos, likes in r.get("rows", []):
            con.execute("INSERT OR REPLACE INTO dias VALUES (?,?,?,?,?,?)",
                        (dia, int(views), int(minutos), int(ganhos), int(perdidos), int(likes)))

    recentes = con.execute("SELECT id, publicado FROM videos WHERE visibilidade = 'public' AND publicado != '' "
                           "ORDER BY publicado DESC LIMIT ?", (VIDEOS_COM_DIAS,)).fetchall()
    for v in recentes:
        desde = v["publicado"][:10]
        ate = min(hoje, dt.date.fromisoformat(desde) + dt.timedelta(days=30)).isoformat()
        r = an.reports().query(ids="channel==MINE", startDate=desde, endDate=ate, metrics="views",
                               dimensions="day", filters=f"video=={v['id']}", sort="day").execute()
        with con:
            for dia, views in r.get("rows", []):
                con.execute("INSERT OR REPLACE INTO video_dias VALUES (?,?,?)", (v["id"], dia, int(views)))
    n = con.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    thumbs = [(r["id"], r["thumb"]) for r in con.execute("SELECT id, thumb FROM videos")]
    con.close()
    baixar_thumbs(thumbs)
    # Etapa 4: comentários (sempre) e análises (a cada 6 h). Um falhar não derruba o resto.
    from jarvis.youtube import analises, avisos, comentarios
    antes = {x["id"] for x in comentarios.listar(100000)}
    for parte, fazer in (("comentários", lambda: comentarios.sincronizar(yt)), ("análises", lambda: analises.sincronizar(an))):
        try:
            fazer()
        except Exception as e:  # noqa: BLE001
            print(f"  painel: {parte}: {e}", flush=True)
    # Etapa 6: o que o Jarvis fala sozinho (perguntas novas e marcos).
    perguntas = [x for x in comentarios.listar(200) if x["id"] not in antes and x["pergunta"] and not x["lido"]]
    avisos.conferir(primeira, perguntas)
    return {"canal": c["snippet"]["title"], "videos": n}


THUMBS = conta.PASTA / "thumbs"


def thumb_local(video: str) -> Path:
    return THUMBS / f"{video}.jpg"


def baixar_thumbs(lista: list[tuple[str, str]], baixar=None) -> int:
    """Guarda as thumbs no PC (a janela e o app abrem sem internet). A thumb
    trocada no YouTube mantém o mesmo endereço: renova uma vez por dia."""
    import urllib.request
    baixar = baixar or (lambda url: urllib.request.urlopen(url, timeout=20).read())
    THUMBS.mkdir(parents=True, exist_ok=True)
    n = 0
    for vid, url in lista:
        arq = thumb_local(vid)
        if not url or (arq.exists() and time.time() - arq.stat().st_mtime < 86400):
            continue
        try:
            arq.write_bytes(baixar(url))
            n += 1
        except Exception:  # noqa: BLE001 - sem a thumb a janela mostra o título
            pass
    return n


# -- ler (janela, app, Jarvis) ----------------------------------------------------------------

def _publicado(v) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(v["publicado"].replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return None


def _mil(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def views_ate_o_dia(con, video: str, dias: int) -> int | None:
    """Views do vídeo nos primeiros `dias` dias (do Analytics). None sem dados."""
    linhas = con.execute("SELECT views FROM video_dias WHERE video = ? ORDER BY dia LIMIT ?",
                         (video, dias)).fetchall()
    return sum(x["views"] for x in linhas) if len(linhas) >= dias else None


def _comparacao(con, v) -> str:
    """O último vídeo contra a média dos outros com a mesma idade."""
    pub = _publicado(v)
    if not pub:
        return ""
    idade = max(1, min(30, (dt.datetime.now(dt.timezone.utc) - pub).days))
    outros = [views_ate_o_dia(con, o["id"], idade) for o in con.execute(
        "SELECT id FROM videos WHERE visibilidade = 'public' AND id != ? ORDER BY publicado DESC LIMIT ?",
        (v["id"], VIDEOS_COM_DIAS)).fetchall()]
    outros = [x for x in outros if x]
    if len(outros) < 3:
        return ""
    media = statistics.median(outros)
    rel = v["views"] / media if media else 0
    jeito = "bem acima" if rel >= 1.3 else "acima" if rel >= 1.05 else "na" if rel >= 0.95 else \
        "abaixo" if rel >= 0.7 else "bem abaixo"
    dia = "no 1º dia" if idade == 1 else f"nos primeiros {idade} dias"
    jeito = "na tua média" if jeito == "na" else f"{jeito} da tua média"
    return f"{jeito} ({_mil(int(media))} views {dia})"


def resumo() -> str:
    """O "como tá o canal?" em texto, para o Jarvis falar."""
    if not BANCO.exists():
        return "O painel ainda não tem dados: falta conectar o YouTube."
    con = abrir()
    c = con.execute("SELECT * FROM canal").fetchone()
    if not c:
        return "O painel ainda não tem dados: falta a primeira sincronização."
    partes = [f"Canal {c['titulo']}: {_mil(c['inscritos'])} inscritos e {c['videos']} vídeos."]
    hoje = dt.date.today()
    d28 = con.execute("SELECT SUM(views) v, SUM(minutos) m, SUM(ganhos) - SUM(perdidos) s FROM dias WHERE dia > ?",
                      ((hoje - dt.timedelta(days=28)).isoformat(),)).fetchone()
    antes = con.execute("SELECT SUM(views) v FROM dias WHERE dia > ? AND dia <= ?",
                        ((hoje - dt.timedelta(days=56)).isoformat(), (hoje - dt.timedelta(days=28)).isoformat())).fetchone()
    if d28["v"] is not None:
        sinal = "+" if (d28["s"] or 0) >= 0 else ""
        comp = f" (nos 28 antes: {_mil(antes['v'])})" if antes["v"] else ""
        partes.append(f"Últimos 28 dias: {_mil(d28['v'])} views{comp}, {_mil((d28['m'] or 0) // 60)} horas assistidas "
                      f"e {sinal}{d28['s'] or 0} inscritos.")
    ultimo = con.execute("SELECT * FROM videos WHERE visibilidade = 'public' ORDER BY publicado DESC LIMIT 1").fetchone()
    if ultimo:
        pub = _publicado(ultimo)
        ha = (dt.datetime.now(dt.timezone.utc) - pub).days if pub else 0
        quando = "hoje" if ha == 0 else "ontem" if ha == 1 else f"há {ha} dias"
        comp = _comparacao(con, ultimo)
        partes.append(f"Último vídeo, \"{ultimo['titulo']}\" ({quando}): {_mil(ultimo['views'])} views, "
                      f"{ultimo['likes']} likes, {ultimo['comentarios']} comentários" + (f", {comp}." if comp else "."))
    agendados = con.execute("SELECT titulo, agendado FROM videos WHERE agendado != '' ORDER BY agendado").fetchall()
    for a in agendados:
        quando = dt.datetime.fromisoformat(a["agendado"].replace("Z", "+00:00")).astimezone()
        partes.append(f"Agendado: \"{a['titulo']}\" para {quando:%d/%m às %H:%M}.")
    idade = (time.time() - c["atualizado"]) / 60
    if idade > 90:
        partes.append(f"(Dados de {idade / 60:.0f} h atrás: o PC não conseguiu atualizar.)")
    con.close()
    return " ".join(partes)


def achar_video(falado: str) -> list[dict]:
    """Os vídeos cujo título tem as palavras faladas ("o do Doors" -> Doors)."""
    palavras = [p for p in re.findall(r"\w+", _sem_acento(falado)) if len(p) > 2
                and p not in {"video", "que", "dos", "das", "como", "foi", "esse", "aquele"}]
    if not palavras or not BANCO.exists():
        return []
    con = abrir()
    achados = []
    for v in con.execute("SELECT * FROM videos ORDER BY publicado DESC").fetchall():
        nota = sum(p in _sem_acento(v["titulo"]) for p in palavras)
        if nota:
            achados.append((nota, dict(v)))
    con.close()
    melhor = max((n for n, _ in achados), default=0)
    return [v for n, v in achados if n == melhor]


def sobre_video(falado: str) -> str:
    achados = achar_video(falado)
    if not achados:
        return "Não achei nenhum vídeo com esse nome."
    con = abrir()
    linhas = []
    for v in achados[:3]:
        pub = _publicado(v)
        comp = _comparacao(con, v)
        data = f"{pub.astimezone():%d/%m/%Y}" if pub else "sem data"
        linhas.append(f"\"{v['titulo']}\" ({data}, {v['visibilidade']}): "
                      f"{_mil(v['views'])} views, {v['likes']} likes, {v['comentarios']} comentários"
                      + (f", {comp}" if comp else "") + f". Link: https://youtu.be/{v['id']}")
    con.close()
    return "\n".join(linhas)


# -- para a janela e o app ------------------------------------------------------------------

def _numeros(con, hoje: dt.date) -> dict:
    def soma(de: int, ate: int):
        return con.execute("SELECT COALESCE(SUM(views),0) v, COALESCE(SUM(minutos),0) m, "
                           "COALESCE(SUM(ganhos)-SUM(perdidos),0) s, COUNT(*) n FROM dias WHERE dia > ? AND dia <= ?",
                           ((hoje - dt.timedelta(days=de)).isoformat(), (hoje - dt.timedelta(days=ate)).isoformat())).fetchone()
    agora, antes = soma(28, 0), soma(56, 28)

    def variacao(a, b):
        return None if not b else round(100 * (a - b) / b)
    return {"views28": agora["v"], "horas28": agora["m"] // 60, "inscritos28": agora["s"],
            "views28_var": variacao(agora["v"], antes["v"]), "horas28_var": variacao(agora["m"], antes["m"]),
            "inscritos28_antes": antes["s"]}


def meta(inscritos: int) -> int:
    """A próxima marca redonda: 100, 250, 500, 1.000, 2.500, 5.000, 10.000..."""
    base = 100
    while True:
        for m in (1, 2.5, 5):
            if inscritos < base * m:
                return int(base * m)
        base *= 10


def para_janela(hoje: dt.date | None = None) -> dict:
    hoje = hoje or dt.date.today()
    if not BANCO.exists():
        return {"conectado": conta.conectado(), "temDados": False}
    con = abrir()
    c = con.execute("SELECT * FROM canal").fetchone()
    if not c:
        con.close()
        return {"conectado": conta.conectado(), "temDados": False}
    videos = []
    for v in con.execute("SELECT * FROM videos ORDER BY COALESCE(NULLIF(agendado,''), publicado) DESC"):
        arq = thumb_local(v["id"])
        videos.append({"id": v["id"], "titulo": v["titulo"], "descricao": v["descricao"], "publicado": v["publicado"],
                       "duracao": v["duracao_s"], "views": v["views"], "likes": v["likes"],
                       "comentarios": v["comentarios"], "visibilidade": v["visibilidade"], "agendado": v["agendado"],
                       "tags": json.loads(v["tags"] or "[]"),
                       "thumb": arq.as_uri() if arq.exists() else "",
                       "comparacao": _comparacao(con, v) if v["visibilidade"] == "public" else ""})
    dias = [dict(d) for d in con.execute("SELECT * FROM dias WHERE dia > ? ORDER BY dia",
                                         ((hoje - dt.timedelta(days=90)).isoformat(),))]
    r = {"conectado": conta.conectado(), "temDados": True, "atualizado": c["atualizado"],
         "canal": {"titulo": c["titulo"], "inscritos": c["inscritos"], "views": c["views"], "videos": c["videos"],
                   "meta": meta(c["inscritos"])},
         "numeros": _numeros(con, hoje), "dias": dias, "videos": videos}
    con.close()
    from jarvis.youtube import analises, comentarios, producao
    producao.ligar_postados()
    r["cards"] = producao.listar()
    r["comentarios"] = comentarios.listar()
    r["naoLidos"] = comentarios.nao_lidos()
    r["analises"] = analises.para_janela()
    return r


def dias_do_video(video: str) -> list[dict]:
    if not BANCO.exists():
        return []
    con = abrir()
    r = [{"dia": d["dia"], "views": d["views"]} for d in
         con.execute("SELECT dia, views FROM video_dias WHERE video = ? ORDER BY dia", (video,))]
    con.close()
    return r
