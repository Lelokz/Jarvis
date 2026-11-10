"""Painel do Canal, etapa 1 (09/11/2026): sincronizar e responder "como tá
o canal?" / "como foi o vídeo do Doors?". YouTube de mentira: nada sai do PC.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ["JARVIS_DADOS"] = tempfile.mkdtemp(prefix="jarvis-canal-")

from jarvis.canal import conta, dados  # noqa: E402

ok = falhou = 0
HOJE = dt.date.today()


def checa(nome, cond, detalhe=""):
    global ok, falhou
    if cond:
        ok += 1
        print(f"  PASSOU  {nome}", flush=True)
    else:
        falhou += 1
        print(f"  FALHOU  {nome}  {detalhe}", flush=True)


class Pedido:
    def __init__(self, resposta):
        self.resposta = resposta

    def execute(self):
        return self.resposta


def iso(dias_atras: int, hora: int = 18) -> str:
    # "há N dias" exato a qualquer hora do dia: N dias e 1 hora atrás.
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=dias_atras, hours=1)).replace(
        microsecond=0).isoformat().replace("+00:00", "Z")


# 20 vídeos: o mais novo (há 3 dias) é o "Doors", os outros um por semana.
VIDEOS = [{"id": f"v{i}", "titulo": "DOORS: o hotel inteiro" if i == 0 else f"Minecraft 100% ep {i}",
           "pub": 3 if i == 0 else 7 * i, "views": 900 if i == 0 else 2000 + i} for i in range(20)]
VIDEOS.append({"id": "agend", "titulo": "Roblox novo", "pub": None, "views": 0})


class YT:
    def __init__(self):
        self.paginas = 0

    def channels(self):
        return self

    def playlistItems(self):
        return self

    def videos(self):
        return self

    def list(self, **kw):
        if "mine" in kw:
            return Pedido({"items": [{"id": "UC1", "snippet": {"title": "Lelokz", "thumbnails": {}},
                                      "statistics": {"subscriberCount": "913", "viewCount": "50000", "videoCount": "21"},
                                      "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})
        if "playlistId" in kw:
            # Duas páginas, para provar que segue o nextPageToken.
            self.paginas += 1
            metade = VIDEOS[:12] if not kw.get("pageToken") else VIDEOS[12:]
            r = {"items": [{"contentDetails": {"videoId": v["id"]}} for v in metade]}
            if not kw.get("pageToken"):
                r["nextPageToken"] = "p2"
            return Pedido(r)
        ids = kw["id"].split(",")
        itens = []
        for v in VIDEOS:
            if v["id"] in ids:
                status = {"privacyStatus": "public"} if v["pub"] is not None else \
                    {"privacyStatus": "private", "publishAt": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2))
                     .replace(hour=21, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")}
                itens.append({"id": v["id"], "snippet": {"title": v["titulo"], "publishedAt": iso(v["pub"]) if v["pub"] is not None else "",
                                                          "tags": ["doors"], "thumbnails": {"high": {"url": "http://t"}}},
                              "statistics": {"viewCount": str(v["views"]), "likeCount": "40", "commentCount": "7"},
                              "status": status, "contentDetails": {"duration": "PT1H2M3S"}})
        return Pedido({"items": itens})


class AN:
    def reports(self):
        return self

    def query(self, **kw):
        if "filters" in kw:
            vid = kw["filters"].split("==")[1]
            v = next(x for x in VIDEOS if x["id"] == vid)
            inicio = dt.date.fromisoformat(kw["startDate"])
            fim = dt.date.fromisoformat(kw["endDate"])
            por_dia = 300 if vid == "v0" else 200  # o Doors vai melhor por dia
            n = (fim - inicio).days + 1
            return Pedido({"rows": [[(inicio + dt.timedelta(days=d)).isoformat(), por_dia] for d in range(n)]})
        return Pedido({"rows": [[(HOJE - dt.timedelta(days=d)).isoformat(), 100, 600, 2, 1, 5] for d in range(60)]})


def main() -> int:
    print("-- sem conexão --")
    checa("sem token: não conectado", not conta.conectado())
    checa("resumo avisa que falta conectar", "falta conectar" in dados.resumo())

    print("-- sincronizar --")
    yt = YT()
    r = dados.sincronizar(yt, AN())
    checa("leu o canal e os 21 vídeos", r == {"canal": "Lelokz", "videos": 21}, r)
    checa("seguiu as duas páginas da lista de vídeos", yt.paginas == 2)
    con = dados.abrir()
    v = con.execute("SELECT * FROM videos WHERE id = 'v0'").fetchone()
    checa("duração 1h02m03s", v["duracao_s"] == 3723)
    checa("agendado guardado", con.execute("SELECT agendado FROM videos WHERE id = 'agend'").fetchone()[0] != "")
    checa("os dias do canal", con.execute("SELECT COUNT(*) FROM dias").fetchone()[0] == 60)
    con.close()
    VIDEOS.pop(5)
    dados.sincronizar(YT(), AN())
    con = dados.abrir()
    checa("vídeo apagado no YouTube sai daqui", con.execute("SELECT COUNT(*) FROM videos WHERE id = 'v5'").fetchone()[0] == 0)
    con.close()

    print("-- como tá o canal --")
    s = dados.resumo()
    print("   ", s)
    checa("inscritos", "913 inscritos" in s)
    checa("28 dias com comparação", "2.800 views (nos 28 antes: 2.800)" in s, s)
    checa("último vídeo e quando", "\"DOORS: o hotel inteiro\" (há 3 dias)" in s, s)
    checa("compara com a média", "acima da tua média" in s, s)
    checa("o agendado", "Agendado: \"Roblox novo\"" in s, s)

    print("-- como foi o vídeo do Doors --")
    s = dados.sobre_video("como foi o vídeo do doors?")
    checa("acha pelo nome falado", s.startswith("\"DOORS: o hotel inteiro\"") and "youtu.be/v0" in s, s)
    checa("nome que não existe", dados.sobre_video("vídeo de culinária") == "Não achei nenhum vídeo com esse nome.")

    print("-- etapa 2: a janela e a edição --")
    from jarvis.canal import editar
    j = dados.para_janela()
    checa("janela recebe canal, números, dias e vídeos", j["temDados"] and j["canal"]["inscritos"] == 913
          and len(j["dias"]) >= 60 and len(j["videos"]) == 20, {k: j.get(k) for k in ("temDados",)})
    checa("meta: 913 -> 1.000; 1.000 -> 2.500; 40 -> 100", (dados.meta(913), dados.meta(1000), dados.meta(40)) == (1000, 2500, 100))
    checa("o agendado vem primeiro na lista", j["videos"][0]["id"] == "agend", j["videos"][0]["id"])
    dados.baixar_thumbs([("v0", "http://t")], baixar=lambda url: b"jpg")
    checa("thumb guardada no PC", dados.thumb_local("v0").read_bytes() == b"jpg")
    checa("e a janela usa a do PC", dados.para_janela()["videos"][1]["thumb"].startswith("file://"))

    class YTEdit:
        enviado = None

        def videos(self):
            return self

        def list(self, **kw):
            return Pedido({"items": [{"snippet": {"title": "velho", "categoryId": "20", "defaultLanguage": "pt"},
                                      "status": {"privacyStatus": "private", "publishAt": "2026-12-01T21:00:00Z",
                                                 "selfDeclaredMadeForKids": False}}]})

        def update(self, part, body):
            YTEdit.enviado = body
            return Pedido({})
    yt = YTEdit()
    editar.salvar_video("agend", "Roblox NOVO", "desc", ["roblox", " ", "lelokz"], "private", yt=yt)
    e = YTEdit.enviado
    checa("manda a categoria de volta (o YouTube exige)", e["snippet"]["categoryId"] == "20" and e["snippet"]["title"] == "Roblox NOVO")
    checa("tags limpas", e["snippet"]["tags"] == ["roblox", "lelokz"])
    checa("privado continua agendado", e["status"].get("publishAt") == "2026-12-01T21:00:00Z")
    editar.salvar_video("agend", "Roblox NOVO", "desc", [], "public", yt=yt)
    checa("público deixa de ser agendado", "publishAt" not in YTEdit.enviado["status"])
    con = dados.abrir()
    linha = con.execute("SELECT titulo, visibilidade, agendado FROM videos WHERE id = 'agend'").fetchone()
    con.close()
    checa("o banco do PC acompanha", tuple(linha) == ("Roblox NOVO", "public", ""), tuple(linha))
    for nome, args in (("título vazio", ("", "", [], "public")), ("título com mais de 100", ("x" * 101, "", [], "public")),
                       ("< no título", ("a <b>", "", [], "public")), ("tags demais", ("ok", "", ["x" * 60] * 10, "public"))):
        try:
            editar.conferir(*args)
            checa(f"recusa {nome}", False)
        except editar.Recusado:
            checa(f"recusa {nome}", True)

    print("-- etapa 3: produção e agendar --")
    from jarvis.canal import producao
    i1 = producao.criar({"titulo": "  ideia   do Doors  ", "jogo": "Doors", "data": "2026-12-01"})
    i2 = producao.criar({"titulo": "minecraft 100 ep 9", "coluna": "editando", "arquivos": ["/a.mov", "/a.mov", "/b.mp4"]})
    l = {c["id"]: c for c in producao.listar()}
    checa("cria com título limpo e começa em Ideia", l[i1]["titulo"] == "ideia do Doors" and l[i1]["coluna"] == "ideia")
    checa("arquivo repetido entra uma vez", l[i2]["arquivos"] == ["/a.mov", "/b.mp4"])
    producao.mover(i1, "gravando")
    checa("mover de etapa", {c["id"]: c for c in producao.listar()}[i1]["coluna"] == "gravando")
    for nome, campos in (("título vazio", {"titulo": "  "}), ("coluna que não existe", {"titulo": "x", "coluna": "lixo"}),
                         ("data errada", {"titulo": "x", "data": "1/12"})):
        try:
            producao.criar(campos)
            checa(f"recusa card com {nome}", False)
        except ValueError:
            checa(f"recusa card com {nome}", True)
    checa("título parecido acha o vídeo", producao.parecidos("Doors hotel inteiro", "DOORS: o hotel inteiro"))
    checa("título diferente não", not producao.parecidos("Minecraft ep 3", "DOORS: o hotel inteiro"))
    i3 = producao.criar({"titulo": "doors o hotel inteiro", "coluna": "pronto"})
    i4 = producao.criar({"titulo": "Roblox NOVO", "coluna": "pronto"})
    producao.ligar_postados()
    l = {c["id"]: c for c in producao.listar()}
    checa("vídeo publicado: card vai pra Postado sozinho", l[i3]["coluna"] == "postado" and l[i3]["video"] == "v0", l[i3])
    checa("e o card de vídeo público também", l[i4]["coluna"] == "postado" and l[i4]["video"] == "agend", l[i4])
    producao.apagar(i4)
    checa("apagar", i4 not in {c["id"] for c in producao.listar()})
    checa("a janela recebe os cards", len(dados.para_janela()["cards"]) == 3)

    import datetime as _dt
    amanha = _dt.datetime.now() + _dt.timedelta(days=1)
    q = editar.quando_de(f"{amanha:%d/%m/%Y}", "18:30")
    checa("data e hora do Léo viram horário com fuso", q.hour == 18 and q.minute == 30 and q.tzinfo is not None)
    for nome, args in (("passado", ("01/01/2020", "10:00")), ("formato errado", ("2026-12-01", "18h"))):
        try:
            editar.quando_de(*args)
            checa(f"recusa agendar no {nome}", False)
        except editar.Recusado:
            checa(f"recusa agendar no {nome}", True)

    class YTAg:
        enviado = None
        status = {"privacyStatus": "private", "selfDeclaredMadeForKids": False}

        def videos(self):
            return self

        def list(self, **kw):
            return Pedido({"items": [{"status": dict(YTAg.status)}]})

        def update(self, part, body):
            YTAg.enviado = (part, body)
            return Pedido({})
    editar.agendar("v1", q, yt=YTAg())
    parte, corpo = YTAg.enviado
    checa("agenda mandando só o status, em UTC", parte == "status" and corpo["status"]["publishAt"].endswith("Z")
          and corpo["status"]["privacyStatus"] == "private", corpo)
    con = dados.abrir()
    checa("o banco do PC fica agendado", con.execute("SELECT agendado FROM videos WHERE id = 'v1'").fetchone()[0] != "")
    con.close()
    editar.desagendar("v1", yt=YTAg())
    checa("tirar do agendamento: sem publishAt e continua privado", "publishAt" not in YTAg.enviado[1]["status"]
          and YTAg.enviado[1]["status"]["privacyStatus"] == "private")
    YTAg.status = {"privacyStatus": "public"}
    try:
        editar.agendar("v1", q, yt=YTAg())
        checa("não agenda vídeo que já saiu", False)
    except editar.Recusado:
        checa("não agenda vídeo que já saiu", True)

    print("-- etapa 4: comentários e análises --")
    from jarvis.canal import analises, comentarios

    def th(i, autor_canal, texto, horas, respostas=()):
        quando = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=horas)).isoformat().replace("+00:00", "Z")
        return {"id": f"t{i}", "snippet": {"videoId": "v0", "totalReplyCount": len(respostas), "topLevelComment": {"snippet": {
                    "authorDisplayName": f"@pessoa{i}", "authorChannelId": {"value": autor_canal}, "textOriginal": texto,
                    "publishedAt": quando, "likeCount": 3}}},
                "replies": {"comments": [{"snippet": {"authorChannelId": {"value": c}}} for c in respostas]}}
    paginas = [[th(1, "X", "quando sai a parte 2?", 2), th(2, "Y", "muito bom", 5, respostas=("UC1",)),
                th(3, "UC1", "valeu galera", 6)], [th(4, "Z", "conteúdo antigo", 24 * 30)]]

    class YTC:
        pedidos = 0

        def commentThreads(self):
            return self

        def list(self, **kw):
            YTC.pedidos += 1
            i = 1 if kw.get("pageToken") else 0
            r = {"items": paginas[i]}
            if i == 0:
                r["nextPageToken"] = "p2"
            return Pedido(r)

        def comments(self):
            return self

        def insert(self, part, body):
            YTC.resposta = body
            return Pedido({})
    novos = comentarios.sincronizar(YTC())
    c = {x["id"]: x for x in comentarios.listar()}
    checa("leu as duas páginas (4 comentários)", novos == 4 and len(c) == 4, novos)
    checa("pergunta marcada", c["t1"]["pergunta"] == 1 and c["t2"]["pergunta"] == 0)
    checa("respondido pelo canal", c["t2"]["respondido"] == 1 and c["t1"]["respondido"] == 0)
    checa("comentário do próprio Lelokz já entra lido", c["t3"]["lido"] == 1)
    checa("na primeira vez, o de 1 mês atrás entra lido", c["t4"]["lido"] == 1 and c["t1"]["lido"] == 0)
    checa("novos = os não lidos", comentarios.nao_lidos() == 2)
    checa("tem o título do vídeo", c["t1"]["video_titulo"] == "DOORS: o hotel inteiro")
    comentarios.marcar_lido(["t1"])
    comentarios.sincronizar(YTC())
    checa("lido continua lido depois de sincronizar de novo", {x["id"]: x for x in comentarios.listar()}["t1"]["lido"] == 1)
    comentarios.responder("t2", "  valeu!  ", yt=YTC())
    checa("responder manda o texto e o comentário certo", YTC.resposta == {"snippet": {"parentId": "t2", "textOriginal": "valeu!"}})
    try:
        comentarios.responder("t2", "   ", yt=YTC())
        checa("não manda resposta vazia", False)
    except editar.Recusado:
        checa("não manda resposta vazia", True)
    comentarios.marcar_lido(None)
    checa("marcar todos como lidos", comentarios.nao_lidos() == 0)

    class ANA:
        pedidos = 0

        def reports(self):
            return self

        def query(self, **kw):
            ANA.pedidos += 1
            dim = kw["dimensions"]
            return Pedido({"rows": {"video": [["v0", 900, 12, 3000]],
                                    "insightTrafficSourceType": [["YT_SEARCH", 300], ["SUGGESTED_VIDEO", 500], ["RELATED_VIDEO", 100], ["XYZ_NOVO", 5]],
                                    "country": [["BR", 800], ["PT", 50]],
                                    "ageGroup": [["age13-17", 40.0], ["age65-", 1.5]],
                                    "deviceType": [["MOBILE", 700], ["DESKTOP", 200]]}[dim]})
    analises.sincronizar(ANA())
    a = analises.para_janela()
    checa("origens em português e somadas (sugeridos 500+100)", a["origens"][0] == {"nome": "Vídeos sugeridos", "valor": 600}, a["origens"])
    checa("origem desconhecida não some", any(o["nome"] == "Xyz Novo" for o in a["origens"]))
    checa("países e aparelhos em português", a["paises"][0]["nome"] == "Brasil" and a["aparelhos"][0]["nome"] == "Celular")
    checa("idades 13–17 e 65+", [x["nome"] for x in a["idades"]] == ["13–17", "65+"])
    checa("os vídeos que mais trouxeram views", a["top"][0] == {"video": "v0", "views": 900, "inscritos": 12, "minutos": 3000})
    n = ANA.pedidos
    analises.sincronizar(ANA())
    checa("não pergunta de novo antes de 6 h", ANA.pedidos == n)
    j = dados.para_janela()
    checa("a janela recebe comentários, novos e análises", len(j["comentarios"]) == 4 and j["naoLidos"] == 0 and "origens" in j["analises"])

    print(f"\n{ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
