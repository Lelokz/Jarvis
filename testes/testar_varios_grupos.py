"""Vários grupos do WhatsApp (09/11/2026): marcar/desmarcar, cada grupo com a
própria leitura e limite (50 por hora), e o pedido aprovado volta pro grupo
certo. Sem WhatsApp nem Claude de verdade: ajustes e aprovações em pasta temporária.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from jarvis import ajustes  # noqa: E402
from jarvis.grupo import familia  # noqa: E402
from jarvis.nucleo import aprovacoes  # noqa: E402

ok = falhou = 0
A, B, C = "111@g.us", "222@g.us", "333@g.us"


def checa(nome, cond, detalhe=""):
    global ok, falhou
    if cond:
        ok += 1
        print(f"  PASSOU  {nome}", flush=True)
    else:
        falhou += 1
        print(f"  FALHOU  {nome}  {detalhe}", flush=True)


class WhatsAppFalso:
    def __init__(self):
        self.mandadas: list[tuple[str, str]] = []
        self.msgs: dict[str, list[tuple[str, int, str, dt.datetime, str]]] = {}
        self.reacoes: list[tuple[str, str, str, str]] = []
        self.n = 0

    def nome_de(self, jid):
        return {A: "Família", B: "Amigos", C: "Escola"}.get(jid, "?")

    def meu_jid(self):
        return "5500@s.whatsapp.net"

    def enviar(self, jid, texto, arquivo=None):
        self.mandadas.append((jid, texto))
        return True, ""

    def eu_mandei_desde(self, jid, desde):
        return []

    def _quando(self, t):
        return t

    def reagir(self, chat, id_msg, remetente, emoji):
        self.reacoes.append((chat, id_msg, remetente, emoji))
        return True

    def _consultar(self, _sql, args):
        jid, quantas = args
        return list(reversed(self.msgs.get(jid, [])))[:quantas]

    def chega(self, jid, quem, texto, eu=False):
        self.n += 1
        self.msgs.setdefault(jid, []).append((quem, int(eu), texto, dt.datetime.now(), f"M{self.n}"))
        return f"M{self.n}"

    def bot_fala(self, jid, texto):  # o que o Jarvis mandou aparece como mensagem "minha"
        self.chega(jid, "5500", texto, eu=True)


def main() -> int:
    pasta = Path(tempfile.mkdtemp(prefix="jarvis-grupos-"))
    ajustes.ARQUIVO = pasta / "ajustes.json"
    aprovacoes.ARQUIVO = pasta / "aprovacoes.json"

    print("-- V1. o arquivo antigo (um grupo só) vira lista --")
    ajustes.ARQUIVO.write_text(json.dumps({"grupo_jid": A, "grupo_ligado": True}))
    checa("o grupo antigo entra na lista", ajustes.ler()["grupos"] == [A], ajustes.ler())
    checa("e continua ligado", ajustes.grupos_ativos() == [A])

    print("-- V2. marcar e desmarcar pelo Conectar --")
    from jarvis import conectar
    import sqlite3
    banco = pasta / "messages.db"
    con = sqlite3.connect(banco)
    con.execute("CREATE TABLE chats (jid TEXT, name TEXT, last_message_time TEXT)")
    con.executemany("INSERT INTO chats VALUES (?,?,?)", [(A, "Família", "3"), (B, "Amigos", "2"), (C, "Escola", "1")])
    con.commit(); con.close()

    class Cfg:
        class whatsapp:
            pass
    Cfg.whatsapp.banco = str(banco)
    r = conectar._grupo(Cfg, "escolher", B, None)
    checa("marcar o segundo não desmarca o primeiro", r["escolhidos"] == [A, B], r)
    r = conectar._grupo(Cfg, "escolher", C, None)
    checa("três marcados", r["escolhidos"] == [A, B, C] and r["estado"] == "conectado", r)
    r = conectar._grupo(Cfg, "escolher", B, None)
    checa("tocar de novo desmarca só aquele", r["escolhidos"] == [A, C], r)
    checa("o app antigo ainda recebe um 'escolhido'", r["escolhido"] == A, r)
    conectar._grupo(Cfg, "escolher", A, None)
    r = conectar._grupo(Cfg, "escolher", C, None)
    checa("sem nenhum, desliga", r["escolhidos"] == [] and r["ligado"] is False, r)
    r = conectar._grupo(Cfg, "escolher", B, None)
    checa("o primeiro marcado liga sozinho", r["escolhidos"] == [B] and r["ligado"] is True, r)
    conectar._grupo(Cfg, "escolher", A, None)

    print("-- V3. o Jarvis atende cada grupo separado --")
    w = WhatsAppFalso()
    g = familia.GrupoFamilia(w, "claude", "sonnet", app_desde=lambda: None)
    atendidos: list[tuple[str, list]] = []
    detalhes: list[tuple[str, str, list, list]] = []
    responde = {"sim": True}

    async def atender_falso(jid, persona, chamadas, seguidas=None, recados_da_hora=None):
        seguidas = seguidas or []
        atendidos.append((jid, [m.texto for m in chamadas + seguidas]))
        detalhes.append((jid, persona, [m.texto for m in chamadas], [m.texto for m in seguidas]))
        if responde["sim"]:  # como se ele tivesse usado o `responder`: abre a conversa com quem falou
            g._abrir(jid, persona, chamadas + seguidas)
    g._atender = atender_falso
    w.chega(A, "Tia", "Jarvis, mensagem velha")
    g._uma_volta()  # primeira volta: marca onde começa, não responde o velho
    checa("não responde mensagem de antes", atendidos == [], atendidos)
    w.chega(A, "Chris", "Jarvis, que horas são?")
    w.chega(B, "Pedro", "jarvis conta uma piada")
    w.chega(B, "Pedro", "conversa sem chamar")
    g._uma_volta()
    checa("respondeu nos dois grupos, cada um com a sua mensagem",
          sorted(atendidos) == [(A, ["Jarvis, que horas são?"]), (B, ["jarvis conta uma piada"])], atendidos)

    print("-- V3b. conversa aberta só com quem ele respondeu --")
    atendidos.clear(); detalhes.clear()
    w.chega(A, "Chris", "e amanhã?")              # o Chris falou com ele: continua sem "Jarvis"
    w.chega(A, "Tia", "alguém viu minha chave?")  # a Tia não: conversa do grupo, nem chega nele
    g._uma_volta()
    checa("a mensagem do Chris chega como continuação",
          detalhes == [(A, "jarvis", [], ["e amanhã?"])], detalhes)
    checa("a da Tia nem chega nele", all("chave" not in t for _, ts in atendidos for t in ts), atendidos)
    checa("continuação não ganha 👀", all(r[1] != w.msgs[A][-2][4] for r in w.reacoes), w.reacoes)

    print("-- V3c. o 👀 na mensagem de quem chamou --")
    w.reacoes.clear()
    mid = w.chega(A, "Tia", "Jarvis, me lembra do remédio às 20h")
    g._uma_volta()
    checa("reagiu com 👀 na mensagem certa", (A, mid, "Tia", "👀") in w.reacoes, w.reacoes)
    w.reacoes.clear()
    mid = w.chega(A, "5500", "Jarvis, testa aí", eu=True)
    g._uma_volta()
    checa("na mensagem do dono também (sem remetente: a ponte põe o dono)", (A, mid, "", "👀") in w.reacoes, w.reacoes)

    print("-- V3d. a Friday no grupo --")
    atendidos.clear(); detalhes.clear()
    w.chega(B, "Pedro", "Friday, qual o melhor anime?")
    w.chega(B, "Ana", "Jarvis e Friday, bom dia")
    g._uma_volta()
    checa("a Friday atende quem chamou ela",
          (B, "friday", ["Friday, qual o melhor anime?"], []) in detalhes, detalhes)
    checa("quem chama os dois vai pra quem foi chamado primeiro",
          (B, "jarvis", ["Jarvis e Friday, bom dia"], []) in detalhes, detalhes)
    w.bot_fala(B, "💜 Friday: Depende do que você curte!")
    detalhes.clear()
    w.chega(B, "Pedro", "curto ação")
    g._uma_volta()
    checa("a continuação do Pedro vai pra Friday, não pro Jarvis",
          detalhes == [(B, "friday", [], ["curto ação"])], detalhes)
    checa("o que a Friday mandou não volta como pedido", all("Depende" not in t for _, ts in atendidos for t in ts))

    print("-- V4. limite de 50 por hora em CADA grupo --")
    atendidos.clear()
    g._chamadas[A] = familia.deque([familia.time.time()] * 50)
    w.chega(A, "Chris", "Jarvis, de novo")
    w.chega(B, "Pedro", "Jarvis, e aí")
    g._uma_volta()
    checa("o grupo cheio não chama o Claude", all(j != A for j, _ in atendidos), atendidos)
    checa("e avisa lá que volta depois", any(j == A and "daqui a pouco" in t for j, t in w.mandadas), w.mandadas)
    checa("o outro grupo continua respondendo", [j for j, _ in atendidos] == [B], atendidos)
    checa("o limite é 50", familia.MAX_POR_HORA == 50)

    print("-- V5. pedido aprovado volta pro grupo de onde veio --")
    a = aprovacoes.criar("Pedro", "abre o Spotify", jid=B)
    aprovacoes.responder(a["id"], False)
    w.mandadas.clear()
    g._uma_volta()
    checa("o 'não liberou' vai pro grupo dos Amigos",
          len(w.mandadas) == 1 and w.mandadas[0][0] == B and "não liberou" in w.mandadas[0][1], w.mandadas)
    a = aprovacoes.criar("Tia", "toca música", jid=A)
    aprovacoes.responder(a["id"], True)
    g._uma_volta()
    saida = g.pegar()
    checa("o aprovado manda responder no grupo certo, com o nome dele",
          saida and saida[0] == "executar" and A in saida[1] and "Família" in saida[1], saida)

    print("-- V6. grupo desmarcado para de ser lido --")
    atendidos.clear()
    conectar._grupo(Cfg, "escolher", B, None)
    w.chega(B, "Pedro", "Jarvis, ainda tá aí?")
    g._uma_volta()
    checa("não responde no grupo desmarcado", all(j != B for j, _ in atendidos), atendidos)

    print(f"\n  {ok} passaram, {falhou} falharam")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
