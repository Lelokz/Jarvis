"""O histórico dos grupos (09/11/2026): o puxador pede ao "celular" as
mensagens de antes da mais antiga, de 50 em 50, até acabar, e escreve o
historico.txt na pasta do grupo. Sem WhatsApp de verdade: banco sqlite
temporário e uma ponte de mentira que responde inserindo as mensagens velhas.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from jarvis import memorias  # noqa: E402
from jarvis.grupo import familia, historico  # noqa: E402
from jarvis.nucleo.whatsapp import WhatsApp  # noqa: E402

ok = falhou = 0
A, B = "111@g.us", "222@g.us"
INICIO = dt.datetime(2024, 1, 1, 12, 0)


def checa(nome, cond, detalhe=""):
    global ok, falhou
    if cond:
        ok += 1
        print(f"  PASSOU  {nome}", flush=True)
    else:
        falhou += 1
        print(f"  FALHOU  {nome}  {detalhe}", flush=True)


class Banco:
    def __init__(self, caminho: Path):
        self.caminho = caminho
        con = sqlite3.connect(caminho)
        con.execute("CREATE TABLE messages (id TEXT, chat_jid TEXT, sender TEXT, content TEXT, "
                    "timestamp TIMESTAMP, is_from_me BOOLEAN, media_type TEXT, PRIMARY KEY (id, chat_jid))")
        con.commit()
        con.close()

    def por(self, jid, i, minutos, sender, texto, eu=False, midia=""):
        con = sqlite3.connect(self.caminho)
        quando = (INICIO + dt.timedelta(minutes=minutos)).strftime("%Y-%m-%d %H:%M:%S-03:00")
        con.execute("INSERT OR REPLACE INTO messages VALUES (?,?,?,?,?,?,?)",
                    (i, jid, sender, texto, quando, int(eu), midia))
        con.commit()
        con.close()


class Resposta:
    def __init__(self, ok):
        self.ok = ok
        self.content = b"x"

    def json(self):
        return {"success": self.ok}


def main() -> int:
    pasta = Path(tempfile.mkdtemp(prefix="jarvis-historico-"))
    memorias.GRUPOS = pasta / "grupos"
    banco = Banco(pasta / "messages.db")
    w = WhatsApp(pasta / "messages.db", "http://ponte/api/send")
    w.nome_de = lambda jid, nome=None: {"ana@lid": "Ana", "pedro@lid": "Pedro"}.get(jid, "alguém")

    # O grupo A tem 230 mensagens no "celular"; a ponte só tem as 30 últimas.
    TOTAL, TEM = 230, 30
    for n in range(TOTAL - TEM, TOTAL):
        banco.por(A, f"A{n}", n, "ana@lid", f"msg {n}")
    banco.por(B, "B1", 5, "pedro@lid", "oi do outro grupo")

    pedidos = []
    ponte = {"ligada": True}

    def post(url, json=None, timeout=None):
        pedidos.append(json)
        if not ponte["ligada"]:
            raise historico.requests.ConnectionError()
        if url.endswith("/history") and json["chat"] == A:
            antiga = int(json["id"][1:])  # o "celular" manda as 50 de antes
            for n in range(max(0, antiga - json["count"]), antiga):
                banco.por(A, f"A{n}", n, "ana@lid", f"msg {n}")
        return Resposta(True)

    historico.requests.post = post
    g = familia.GrupoFamilia.__new__(familia.GrupoFamilia)
    g.whatsapp = w
    p = historico.Puxador(w, g._quem, tuple(familia.PREFIXOS.values()))

    print("-- H1. pede de 50 em 50 até a primeira mensagem --")
    agora = 1000.0
    estados = []
    for _ in range(30):
        estados.append(p.passo(A, agora))
        agora += historico.ESPERA_S + 1
        if estados[-1] == "acabou":
            break
    n = w._consultar("SELECT COUNT(*) FROM messages WHERE chat_jid = ?", (A,))[0][0]
    checa("chegou tudo (230)", n == TOTAL, str(n))
    checa("4 pedidos que trazem, 4 sem nada, depois acabou", estados.count("pediu") == 4 + historico.SEM_NOVIDADE
          and estados[-1] == "acabou", str(estados))
    checa("o 1º pedido foi da mais antiga que tinha", pedidos[0]["id"] == f"A{TOTAL - TEM}" and pedidos[0]["count"] == 50)
    checa("o horário do pedido é o da mensagem",
          pedidos[0]["timestamp"] == int((INICIO + dt.timedelta(minutes=TOTAL - TEM)).replace(
              tzinfo=dt.timezone(dt.timedelta(hours=-3))).timestamp()))

    print("-- H2. acabou não pede mais (até o dia seguinte) --")
    antes = len(pedidos)
    checa("não pede de novo", p.passo(A, agora + 60) == "acabou" and len(pedidos) == antes)
    checa("um dia depois confere de novo", p.passo(A, agora + historico.REVER_S + 1) == "pediu")

    print("-- H3. ponte fora não conta como 'acabou' --")
    ponte["ligada"] = False
    t = 10_000.0
    res = [p.passo(B, t + i * (historico.ESPERA_S + 1)) for i in range(8)]
    checa("só 'sem ponte'", set(res) == {"sem ponte"}, str(res))
    ponte["ligada"] = True

    print("-- H4. o historico.txt --")
    banco.por(A, "J1", 300, "5500", "🤖 Jarvis: A viagem ficou pra sexta.", eu=True)
    banco.por(A, "L1", 301, "5500", "valeu", eu=True)
    banco.por(A, "F1", 302, "5500", "💜 Friday: Prontinho!", eu=True)
    banco.por(A, "P1", 303, "pedro@lid", "", midia="image")
    banco.por(A, "P2", 304, "pedro@lid", "linha 1\nlinha 2")
    familia.ajustes.nome_de_quem_usa = lambda: "Léo"
    checa("escreveu", p.escrever(A, "Família"))
    texto = (memorias.pasta_do_grupo(A) / historico.ARQUIVO).read_text(encoding="utf-8").splitlines()
    checa("cabeçalho com o nome do grupo", texto[0].startswith('# Histórico do grupo "Família"'))
    checa("a mais antiga primeiro", texto[2] == "[01/01/2024 12:00] Ana: msg 0", texto[2])
    checa("Jarvis sem o prefixo repetido", "[01/01/2024 17:00] Jarvis: A viagem ficou pra sexta." in texto)
    checa("o Léo pelo nome", "[01/01/2024 17:01] Léo: valeu" in texto)
    checa("Friday", "[01/01/2024 17:02] Friday: Prontinho!" in texto)
    checa("foto", "[01/01/2024 17:03] Pedro: (foto)" in texto)
    checa("quebra de linha vira ' / '", "[01/01/2024 17:04] Pedro: linha 1 / linha 2" in texto)
    checa("sem mudança não reescreve", not p.escrever(A, "Família"))
    p.escrever(B, "Amigos")
    tb = (memorias.pasta_do_grupo(B) / historico.ARQUIVO).read_text(encoding="utf-8")
    checa("cada grupo no seu arquivo", "oi do outro grupo" in tb and "msg 0" not in tb)

    print(f"\n{ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
