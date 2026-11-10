"""As Análises do Painel do Canal (etapa 4): de onde vem o público, países,
idade, aparelhos e os vídeos que mais trouxeram views e inscritos, nos
últimos 28 dias. Atualiza a cada 6 horas (os números do YouTube Analytics
chegam com uns 2 dias de atraso, não adianta perguntar mais vezes).
"""

from __future__ import annotations

import datetime as dt
import json
import time

from jarvis.canal import conta, dados

ESQUEMA = "CREATE TABLE IF NOT EXISTS analises (chave TEXT PRIMARY KEY, dados TEXT, atualizado REAL);"
A_CADA_S = 6 * 3600
DIAS = 28

ORIGENS = {"YT_SEARCH": "Busca do YouTube", "SUGGESTED_VIDEO": "Vídeos sugeridos", "RELATED_VIDEO": "Vídeos sugeridos",
           "BROWSE": "Página inicial e Inscrições", "SUBSCRIBER": "Página inicial e Inscrições",
           "EXT_URL": "Sites e apps de fora", "PLAYLIST": "Playlists", "YT_PLAYLIST_PAGE": "Playlists",
           "YT_CHANNEL": "Página do canal", "CHANNEL": "Página do canal", "SHORTS": "Shorts",
           "NOTIFICATION": "Notificações", "NO_LINK_OTHER": "Direto ou desconhecido", "END_SCREEN": "Telas finais",
           "ANNOTATION": "Cards", "CAMPAIGN_CARD": "Cards", "YT_OTHER_PAGE": "Outras páginas do YouTube",
           "HASHTAGS": "Hashtags", "LIVE_REDIRECT": "Lives", "SOUND_PAGE": "Página de som", "PRODUCT_PAGE": "Página de produto",
           "ADVERTISING": "Anúncios", "NO_LINK_EMBEDDED": "Vídeo incorporado em site", "VIDEO_REMIXES": "Remixes"}
PAISES = {"BR": "Brasil", "PT": "Portugal", "US": "Estados Unidos", "AO": "Angola", "MZ": "Moçambique",
          "AR": "Argentina", "PY": "Paraguai", "UY": "Uruguai", "JP": "Japão", "DE": "Alemanha", "ES": "Espanha",
          "FR": "França", "IT": "Itália", "GB": "Reino Unido", "CA": "Canadá", "MX": "México", "CL": "Chile",
          "CO": "Colômbia", "PE": "Peru", "BO": "Bolívia", "VE": "Venezuela", "CV": "Cabo Verde", "ZZ": "Desconhecido"}
APARELHOS = {"MOBILE": "Celular", "DESKTOP": "Computador", "TV": "TV", "TABLET": "Tablet",
             "GAME_CONSOLE": "Videogame", "UNKNOWN_PLATFORM": "Outro"}


def _abrir():
    con = dados.abrir()
    con.executescript(ESQUEMA)
    return con


def _idade(g: str) -> str:
    """age13-17 -> 13–17; age65- -> 65+."""
    g = g.removeprefix("age")
    return g.replace("-", "–") if not g.endswith("-") else g[:-1] + "+"


def sincronizar(an=None, hoje: dt.date | None = None, forcar: bool = False) -> bool:
    con = _abrir()
    ultima = con.execute("SELECT MIN(atualizado) FROM analises").fetchone()[0]
    if not forcar and ultima and time.time() - ultima < A_CADA_S:
        con.close()
        return False
    an = an or conta.analytics()
    hoje = hoje or dt.date.today()
    base = dict(ids="channel==MINE", startDate=(hoje - dt.timedelta(days=DIAS)).isoformat(), endDate=hoje.isoformat())

    def q(**kw):
        return an.reports().query(**base, **kw).execute().get("rows", [])

    def somar(linhas, nomes):
        juntos: dict[str, float] = {}
        for k, v in linhas:
            nome = nomes.get(k, k.replace("_", " ").title())
            juntos[nome] = juntos.get(nome, 0) + v
        return [{"nome": n, "valor": v} for n, v in sorted(juntos.items(), key=lambda x: -x[1])]

    pedacos = {
        "top": [{"video": v, "views": int(a), "inscritos": int(b), "minutos": int(c)} for v, a, b, c in
                q(dimensions="video", metrics="views,subscribersGained,estimatedMinutesWatched", sort="-views", maxResults=10)],
        "origens": somar(q(dimensions="insightTrafficSourceType", metrics="views", sort="-views"), ORIGENS),
        "paises": somar(q(dimensions="country", metrics="views", sort="-views", maxResults=8), PAISES),
        "idades": [{"nome": _idade(g), "valor": round(p, 1)} for g, p in
                   q(dimensions="ageGroup", metrics="viewerPercentage", sort="ageGroup")],
        "aparelhos": somar(q(dimensions="deviceType", metrics="views", sort="-views"), APARELHOS),
    }
    agora = time.time()
    with con:
        for chave, valor in pedacos.items():
            con.execute("INSERT OR REPLACE INTO analises VALUES (?,?,?)", (chave, json.dumps(valor, ensure_ascii=False), agora))
    con.close()
    return True


def para_janela() -> dict:
    if not dados.BANCO.exists():
        return {}
    con = _abrir()
    r = {k: json.loads(v) for k, v in con.execute("SELECT chave, dados FROM analises")}
    con.close()
    return r
